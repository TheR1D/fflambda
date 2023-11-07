# FFLambda
AWS Lambda encoder based on FFmpeg. The idea behind this project is to utilise AWS lambda functions in order to encode videos fast and in scalable way. This project is not production ready, it's just a proof of concept.

![fflambda](https://github.com/TheR1D/fflambda/assets/16740832/49b3826a-a373-443e-81b5-116dbd427b52)

## Deployment
Deploy it using Terraform:
```bash
git clone https://github.com/TheR1D/fflambda.git
cd fflambda/terraform
terraform apply
```
This will create a new lambda functions and all required resources.

## Trigger encoding
In order to trigger encoding you need to upload a video file to the `lambda-ingestor-bucket` s3 bucket. The lambda function will be triggered automatically and will start ingestor job (lambda function). The ingestor lambda function will split video into multiple chunks and create corresponding database records to track encoding progress. Each new record inserts into `chunk_jobs` table in DynamoDB will trigger a new lambda function (encoder) which will encode the chunk and upload it to the `lambda-encoder-bucket` s3 bucket. The last encoding lambda job will call another lambda function "mux" which will merge all chunks into a single video file (including audio) and upload it to the `lambda-encoder-bucket/encoded` s3 bucket. 
