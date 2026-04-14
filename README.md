# Cloud Resume Challenge

A serverless AWS project to host my resume with a visitor counter.

Live: https://resume.sujoyb.in

---

## Tech Stack

- AWS S3 (static hosting)
- CloudFront (CDN + HTTPS)
- API Gateway
- AWS Lambda (Python)
- DynamoDB
- CodePipeline (CI/CD)

---

## Features

- Static resume website
- Visitor counter (GET + POST API)
- Geo logging of visitors
- Fully serverless (no EC2)

---

## API

- `GET /api/visitors` → get count  
- `POST /api/visitors` → increment count  
- `GET /api/logs` → last 50 visits  
- `GET /api/health` → health check  

---

## Cost

~$1.50/month (serverless)

---

## Author

**Sujoy Bhattacharya**  
