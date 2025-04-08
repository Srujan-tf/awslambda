import boto3
import json

def lambda_handler(event, context):
    # Initialize EC2 and SNS clients
    ec2 = boto3.client('ec2')
    sns_client = boto3.client('sns', region_name='us-east-1')
    
    # Default AMI and Subnet
    ami_id = 'ami-06b21ccaeff8cd686'
    subnet_id = 'subnet-05779ac80641873ac'
    
    # Parse parameters
    instance_type = event.get('instance_type', 't2.micro')
    instance_name = event.get('instance_name')  # Must be provided in the event payload

    if not instance_name or not instance_name.startswith("AWSWIN10"):
        error_message = "Error: Instance name must be provided and start with 'AWSWIN10'."
        return {
            'statusCode': 400,
            'body': json.dumps(error_message)
        }

    ebs_root_type = event.get('ebs_root_type', 'gp2')
    ebs_volume_size = event.get('ebs_volume_size', 8)

    default_tags = {
        "owner": "TCS_Exploration_Support_Team@santos.com",
        "team": "Exploration",
        "map_migrated": "d-server-03fdejna2cl70u",
        "application": "Petrel Suite",
        "owner_tower": "Subsurface Applications",
        "contact": "Hayden Long",
        "owner_team": "Exp",
        "tagged_by": "CloudFinOps",
        "environment": "VDI",
        "Name": instance_name
    }

    try:
        # Check for existing instances with the same Name tag
        filters = [
            {'Name': 'tag:Name', 'Values': [instance_name]},
            {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
        ]
        existing_instances = ec2.describe_instances(Filters=filters)

        # If any instances exist with the same Name tag, return an error
        if any(instance for reservation in existing_instances['Reservations'] for instance in reservation['Instances']):
            error_message = f"Error: EC2 instance with name '{instance_name}' already exists. Please contact your cloud administrator."
            sns_client.publish(
                TopicArn='arn:aws:sns:us-east-1:471112994400:ec2sns',  # Replace with your topic ARN
                Subject='EC2 Instance Creation Failed',
                Message=error_message
            )
            return {
                'statusCode': 400,
                'body': json.dumps(error_message)
            }

        # Create the EC2 instance if no duplicates exist
        response = ec2.run_instances(
            InstanceType=instance_type,
            ImageId=ami_id,
            SubnetId=subnet_id,
            MinCount=1,
            MaxCount=1,
            BlockDeviceMappings=[{
                'DeviceName': '/dev/sda1',
                'Ebs': {
                    'VolumeSize': ebs_volume_size,
                    'VolumeType': ebs_root_type
                }
            }],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': k, 'Value': v} for k, v in default_tags.items()]
            }],
            MetadataOptions={
                'HttpEndpoint': 'enabled',
                'HttpPutResponseHopLimit': 1,
                'HttpTokens': 'optional'
            }
        )
        
        # Get the instance ID of the newly created instance
        instance_id = response['Instances'][0]['InstanceId']

        # Notify via SNS
        sns_client.publish(
            TopicArn='arn:aws:sns:us-east-1:471112994400:ec2sns',
            Subject='EC2 Instance Created Successfully',
            Message=f"Success: EC2 Instance {instance_id} created with Name tag {instance_name}."
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps(f"Success: EC2 Instance {instance_id} created with Name tag {instance_name}.")
        }
        
    except Exception as e:
        # Handle errors and notify via SNS
        error_message = f"Error creating instance: {str(e)}"
        sns_client.publish(
            TopicArn='arn:aws:sns:us-east-1:471112994400:ec2sns',
            Subject='EC2 Instance Creation Error',
            Message=error_message
        )
        return {
            'statusCode': 500,
            'body': json.dumps(error_message)
        }
