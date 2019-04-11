.PHONY: package-and-deploy build


package-and-deploy:
	aws cloudformation validate-template --template-body file://product.template.yaml
	aws cloudformation package \
		--template product.template.yaml \
		--s3-bucket $(BUCKET_NAME) \
		--s3-prefix $(BUCKET_PREFIX) \
		--output-template-file \
		product.template-eu-west-1.yaml
	aws cloudformation deploy \
		--template-file product.template-eu-west-1.yaml \
		--stack-name guardduty-master-enabler-2 \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides AssumableOrgRoleArn=arn:aws:iam::778388402036:role/Admin TargetOU=/

build:
	mkdir -p deploy
	cp src/index.py deploy/
	pip install -r requirements.txt -t deploy/
