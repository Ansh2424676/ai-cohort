# Vector Database Notes

## Chroma vs Pinecone

| Feature | Chroma | Pinecone |
|----------|---------|-----------|
| Type | Local Vector Database | Cloud Vector Database |
| Cost | Completely Free | Free Tier Available |
| Hosting | Local Machine | Cloud |
| Setup | Very Easy | Easy |
| Latency | Very Low | Depends on Internet |
| Enterprise Support | Limited | Excellent |
| Authentication | Not Required | API Keys |

---

## Local vs Cloud

Chroma stores vector embeddings on the local machine, making it simple and fast for development. Pinecone stores vectors in the cloud, making it ideal for production systems that require scalability and remote access.

---

## Free Tier

Chroma is completely free because it runs locally.

Pinecone provides a free serverless tier but requires an account.

---

## Latency

Chroma has lower latency because data never leaves the local machine.

Pinecone latency depends on internet connectivity and cloud region.

---

## Ease of Setup

### Chroma

```bash
pip install chromadb
```

### Pinecone

- Create Account
- Generate API Key
- Create Serverless Index

---

## Enterprise Access Control

Pinecone supports API keys, authentication, cloud security, and enterprise deployments.

Chroma is designed mainly for local development and does not provide enterprise access control by default.

---

## Why I Chose Chroma

For this AI Cohort project, I selected Chroma because it is completely free, requires no signup, runs locally, is lightweight, and is perfect for learning embeddings and vector search before using cloud databases like Pinecone.