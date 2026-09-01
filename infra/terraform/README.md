# GCP Infrastructure

이 Terraform 구성은 Stage 14의 기반 리소스만 정의한다.

- Artifact Registry Docker repository (`trpg-mcp`)
- Cloud Run service (`asia-northeast3`, 1 vCPU, 512 MiB)
- Cloud Run runtime service account
- Secret Manager의 Supabase publishable key secret(값은 별도 주입)
- Cloud Logging, Monitoring, Run, Artifact Registry, Secret Manager API 활성화

실제 GCP 계정이나 프로젝트에 적용하기 전 `terraform plan` 결과를 검토한다.
이 저장소에는 `terraform.tfstate`, 실제 `terraform.tfvars`, secret 값이 들어가면 안 된다.

```powershell
terraform init
terraform fmt -check
terraform validate
terraform plan -var-file=terraform.tfvars
```

이미지 빌드·푸시와 Secret Manager 값 등록은 별도 배포 단계에서 수행한다.
Cloud Run은 `allUsers` invoker로 요청을 수신하지만, `/mcp` 인증은 애플리케이션의
Supabase OAuth/JWT 미들웨어가 담당한다.
