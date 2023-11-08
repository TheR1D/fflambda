# FFLambda
AWS Lambda encoder based on FFmpeg. The idea behind this project is to utilise AWS lambda functions in order to encode videos fast and in scalable way. This project is not production ready, it's just a proof of concept.

![fflambda (2)](https://github.com/TheR1D/fflambda/assets/16740832/0bc29780-dc4a-4ebb-96df-d0047396e084)

## Deployment
Deploy it using Terraform:
```bash
git clone https://github.com/TheR1D/fflambda.git
cd fflambda/terraform
terraform apply
```
This will create a new lambda functions and all required resources.

## Trigger Encoding
To trigger encoding simply upload a video file into `lambda-ingestor-bucket`.

## Ingest Lambda
When we upload a new file into `lambda-ingestor-bucket` it will trigger first "ingest" lambda function. This lambda function will demux audio from video, and split video into multiple chunks. Chunks and audio files will uploaded into `lambda-encoder-bucket` s3 and for each video chunk the lambda function will create DynamoDB record to track encoding progress for each video chunk (later will be used by "encode" lambda function).

## Encode Lambda
Each video chunk reocrd inserted to DynamoDB by "ingest" lambda function will trigger "encode" lambda function. Each "encode" lambda function downloads one video chunk from s3 (created by "ingest" lambda) and starts encoding using `ffmpeg`. Once encoding is complete, "encode" lambda function will upload encoded video chunk into `lambda-encoder-bucket` s3 and update `status` field of corresponding record in DynamoDB to **encoded**. And as a last step it will check if all chunks of given video have been encoded and call "mux" lambda function.

## Mux Lambda
The "mux" lambda function is called by "encode" lambda function once all video chunks were encoded. It is a final lambda function to mux all chunks together and audio track. The final video file will be uploaded in to `lambda-encoder-bucket/encoded` s3.

Note that the lambda functions running on ARM based hardware which makes it super cheap.
