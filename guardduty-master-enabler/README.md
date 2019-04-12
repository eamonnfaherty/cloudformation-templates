# product.template
# Description
This creates a few things in your account:
  - It will create a lambda that allows you to add all members of an organisational unit.
  - It will create a custom resource that will trigger that when the stack is created.
  - It will optionally create a CloudWatch Event rule that triggers on the given ScheduledExpression.


## Parameters
The list of parameters for this template:

### AssumableOrgRoleArn 
Type: String  
Description: The IAM Role ARN that can be assumed from the account this template is run in 
### TargetOU 
Type: String  
Description: The path or ou id used to search for members in 
### SpokeIAMPath 
Type: String 
Default: /guardduty-enabler/ 
Description: The path of the spoke role that should be assumed to enable guardduty in 
### SpokeIAMRole 
Type: String 
Default: EnablerFunctionRole 
Description: The name of the spoke role that should be assumed to enable guardduty in 
### ScheduleExpression 
Type: String 
Default: None 
Description: Cron or rate expressions to pass through to an AWS::Events::Rule 

## Resources
The list of resources this template creates:

### EnablerFunctionRole 
Type: AWS::IAM::Role  
### EnablerFunction 
Type: AWS::Serverless::Function 
Description: A lambda function that can be invoked with a param similar to ```{"target_ou": "/"}``` that will get all children within
the target_ou and enable guardduty and invite to the master.
 
### EnablerFunctionCallerRole 
Type: AWS::IAM::Role  
### EnablerFunctionCusomResource 
Type: AWS::Serverless::Function  
### Enable 
Type: Custom::CustomResource  
### EnablerFunctionScheduler 
Type: AWS::Serverless::Function  
### SchedulingRule 
Type: AWS::Events::Rule  
### PermissionForEventsToInvokeLambda 
Type: AWS::Lambda::Permission  

## Outputs
The list of outputs this template exposes:

### EnablerFunctionName 
Description: The Lambda you can invoke with a param of ```{"target_ou": "/"}```
  

