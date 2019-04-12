from betterboto import client as betterboto_client
import json, logging, os
from urllib.request import Request, urlopen

logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)

MAX_LINKED_ACCOUNTS = 1000


def create_detector(guardduty):
    return guardduty.create_detector(Enable=True).get('DetectorId')


def get_or_create_detector(guardduty):
    detectors = guardduty.list_detectors()
    if len(detectors.get('DetectorIds')) == 0:
        return create_detector(guardduty)
    elif len(detectors.get('DetectorIds')) == 1:
        return detectors.get('DetectorIds')[0]
    else:
        raise Exception("Unsupported response: {}".format(detectors))


def get_children(target_ou):
    assumable_org_role_arn = os.environ.get('ASSUMABLE_ORG_ROLE_ARN')
    with betterboto_client.CrossAccountClientContextManager(
            'organizations', assumable_org_role_arn, 'organizations'
    ) as cross_account_organizations:
        if target_ou[0] == "/":
            ou = cross_account_organizations.convert_path_to_ou(target_ou)
        else:
            ou = target_ou
        logger.info("Targeting ou: {}".format(ou))
        children_in_ou = cross_account_organizations.list_children_nested(ParentId=ou, ChildType='ACCOUNT')
        all_accounts_list = cross_account_organizations.list_accounts_single_page().get('Accounts')
        logger.info("listed accounts: {}".format(all_accounts_list))
        all_accounts_dict = {}
        for a in all_accounts_list:
            all_accounts_dict[a.get('Id')] = a
        for c in children_in_ou:
            c.update(all_accounts_dict[c.get('Id')])
        return children_in_ou


def invite_children(master_guardduty, master_detector_id, children, already_invited):
    accounts_to_invite = [
        c.get('Id') for c in children if c.get('Id') not in already_invited
    ]
    logger.info("Going to invite: {}".format(accounts_to_invite))
    response = master_guardduty.invite_members(
        AccountIds=accounts_to_invite,
        DetectorId=master_detector_id,
        DisableEmailNotification=False,
        Message='We would like to invite you to the GuardDuty group'
    )
    logger.info("Finished invite: {}".format(response))
    if len(response.get('UnprocessedAccounts')) > 0:
        raise Exception("There were unprocessed accounts: {}".format(response.get('UnprocessedAccounts')))


def create_members(master_guardduty, master_detector_id, children, already_invited):
    members_to_create = [
        {
            'AccountId': child.get('Id'),
            'Email': child.get('Email'),
        } for child in children if child.get('Id') not in already_invited
    ]
    logger.info("Going to create: {}".format(members_to_create))
    response = master_guardduty.create_members(
        AccountDetails=members_to_create,
        DetectorId=master_detector_id,
    )
    logger.info("Finished create: {}".format(response))
    if len(response.get('UnprocessedAccounts')) > 0:
        raise Exception("UnprocessedAccounts: {}".format(response.get('UnprocessedAccounts')))


def enable_and_accept_children(master_guardduty, master_detector_id, children, my_account_id):
    spoke_iam_path = os.environ.get('SPOKE_IAM_PATH')
    spoke_iam_role = os.environ.get('SPOKE_IAM_ROLE')
    for child in children:
        child_role_arn = "arn:aws:iam::{}:role{}{}".format(child.get('Id'), spoke_iam_path, spoke_iam_role)
        logger.info("Looking at child: {}".format(child))
        if child.get('Id') != my_account_id:
            logger.info("Handing child: {}".format(child))
            with betterboto_client.CrossAccountClientContextManager(
                    'guardduty', child_role_arn, child.get('Id')
            ) as child_guard_duty:
                response = child_guard_duty.list_invitations()
                for invitation in response.get('Invitations', []):
                    if invitation.get('AccountId') == my_account_id and invitation.get(
                            'RelationshipStatus') == 'Invited':
                        invitation_id = invitation.get('InvitationId')
                        child_detector_id = get_or_create_detector(child_guard_duty)
                        child_guard_duty.accept_invitation(
                            DetectorId=child_detector_id,
                            InvitationId=invitation_id,
                            MasterId=my_account_id
                        )
                        response = master_guardduty.start_monitoring_members(
                            AccountIds=[
                                child.get('Id')
                            ],
                            DetectorId=master_detector_id
                        )
                        if len(response.get('UnprocessedAccounts')) > 0:
                            raise Exception("UnprocessedAccounts when starting to monitor: {}".format(
                                response.get('UnprocessedAccounts')))


def handler_custom_resource(e, context):
    rt = e['RequestType']
    try:
        logger.info(rt)
        if rt == 'Create':
            handler(
                {
                    'target_ou': os.environ.get('TARGET_OU')
                },
                context
            )
            send_response(
                e,
                context,
                "SUCCESS",
                {
                    "Message": "Resource creation successful!",
                }
            )
        elif rt == 'Update':
            handler(e, context)
            send_response(e, context, "SUCCESS",
                          {"Message": "Updated"})
        elif rt == 'Delete':
            raise Exception("Delete is not supported for this resource")
        else:
            send_response(e, context, "FAILED",
                          {"Message": "Unexpected"})
    except Exception as ex:
        logger.error(ex)
        send_response(
            e,
            context,
            "FAILED",
            {
                "Message": "Exception"
            }
        )


def handler_scheduler(e, context):
    handler({'target_ou': os.environ.get('TARGET_OU')}, context)


def handler(e, context):
    my_account_id = context.invoked_function_arn.split(':')[4]
    with betterboto_client.ClientContextManager('guardduty') as master_guardduty:
        master_detector_id = get_or_create_detector(master_guardduty)
        children = get_children(e.get('target_ou'))
        logger.info("Found children: {}".format(children))
        response = master_guardduty.list_members_single_page(
            DetectorId=master_detector_id, OnlyAssociated='false'
        )
        previously_invited_children = [c.get('AccountId') for c in response.get('Members')]
        previously_invited_children.append(my_account_id)
        logger.info("Going to invite: {}".format(children))
        create_members(master_guardduty, master_detector_id, children, previously_invited_children)
        invite_children(master_guardduty, master_detector_id, children, previously_invited_children)
        enable_and_accept_children(
            master_guardduty, master_detector_id, children, my_account_id
        )


def send_response(e, c, rs, rd):
    r = json.dumps({
        "Status": rs,
        "Reason": "CloudWatch Log Stream: " + c.log_stream_name,
        "PhysicalResourceId": c.log_stream_name,
        "StackId": e['StackId'],
        "RequestId": e['RequestId'],
        "LogicalResourceId": e['LogicalResourceId'],
        "Data": rd
    })
    d = str.encode(r)
    h = {
        'content-type': '',
        'content-length': str(len(d))
    }
    req = Request(e['ResponseURL'], data=d, method='PUT', headers=h)
    r = urlopen(req)
    logger.info("Status message: {} {}".format(r.msg, r.getcode()))
