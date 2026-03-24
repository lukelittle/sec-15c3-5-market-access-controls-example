# Security Considerations

## Educational Demo vs Production

⚠️ **This is an educational demo, not production-ready code.**

### What This Demo Includes

✅ **Good practices demonstrated**:
- Least-privilege IAM roles (separate role per function)
- VPC isolation for MSK and Lambda
- IAM authentication for Kafka (SASL_IAM)
- Encryption in transit (TLS for MSK)
- Audit trail with correlation IDs
- No hardcoded credentials

### What This Demo Lacks

❌ **Production requirements not implemented**:
- Encryption at rest (MSK, DynamoDB, S3)
- KMS key management
- Secrets Manager for sensitive config
- API authentication/authorization
- Rate limiting on API Gateway
- DDoS protection
- Comprehensive input validation
- SQL injection prevention (if using SQL)
- Penetration testing
- Security scanning (SAST/DAST)
- Compliance certifications (SOC 2, PCI-DSS, etc.)
- Disaster recovery procedures
- Security incident response plan

## Threat Model

### In-Scope Threats (Partially Mitigated)

1. **Unauthorized Kafka Access**
   - Mitigation: IAM authentication
   - Limitation: No fine-grained topic ACLs

2. **Lambda Function Compromise**
   - Mitigation: Least-privilege IAM, VPC isolation
   - Limitation: No runtime protection, no secrets rotation

3. **Data Exfiltration**
   - Mitigation: VPC endpoints, no public internet
   - Limitation: No DLP, no egress filtering

4. **Audit Trail Tampering**
   - Mitigation: Kafka append-only log
   - Limitation: No cryptographic signatures

### Out-of-Scope Threats (Not Addressed)

1. **API Abuse**
   - No authentication on operator console API
   - No rate limiting
   - No request signing

2. **Insider Threats**
   - No separation of duties
   - No approval workflows
   - No audit of operator actions

3. **Supply Chain Attacks**
   - No dependency scanning
   - No image signing
   - No SBOM (Software Bill of Materials)

4. **Advanced Persistent Threats**
   - No anomaly detection
   - No threat intelligence integration
   - No SIEM integration

## IAM Security

### Least-Privilege Roles

Each Lambda has a dedicated role with minimal permissions:

**Order Generator**:
- Write to `orders.v1` topic only
- No read access to other topics
- No DynamoDB access

**Kill Switch Aggregator**:
- Read from `killswitch.commands.v1`
- Write to `killswitch.state.v1`
- Write to DynamoDB state cache
- No access to orders

**Order Router**:
- Read from `orders.v1` and `killswitch.state.v1`
- Write to `orders.gated.v1` and `audit.v1`
- Write to DynamoDB audit table
- No access to commands topic

**Operator Console**:
- Write to `killswitch.commands.v1` only
- No read access
- No DynamoDB access

### IAM Best Practices Applied

✅ **Implemented**:
- Separate role per function
- No wildcard permissions (where possible)
- Explicit resource ARNs
- Principle of least privilege

❌ **Not implemented** (for production):
- IAM policy conditions (IP restrictions, MFA)
- Service Control Policies (SCPs)
- Permission boundaries
- Regular access reviews
- Automated policy validation

## Network Security

### VPC Isolation

**Architecture**:
- MSK and Lambda in private subnets
- No public IP addresses
- VPC endpoints for AWS services (S3, DynamoDB, CloudWatch)
- Security groups restrict traffic

**Benefits**:
- No direct internet access
- Reduced attack surface
- Network-level isolation

**Limitations**:
- No network segmentation (all in same VPC)
- No WAF (Web Application Firewall)
- No network monitoring/IDS

### Security Groups

**MSK Security Group**:
- Ingress: Port 9098 from Lambda security group only
- Egress: All (for Kafka inter-broker)

**Lambda Security Group**:
- Ingress: None (Lambda doesn't accept inbound)
- Egress: All (needs to reach MSK, VPC endpoints)

**Improvements for production**:
- Restrict egress to specific ports/destinations
- Add network ACLs
- Implement VPC Flow Logs
- Add traffic inspection (AWS Network Firewall)

## Data Security

### Encryption in Transit

✅ **Implemented**:
- MSK uses TLS (SASL_SSL)
- API Gateway uses HTTPS
- AWS service calls use TLS

❌ **Not implemented**:
- Certificate pinning
- Mutual TLS (mTLS)
- Custom CA certificates

### Encryption at Rest

❌ **Not implemented** (for cost/simplicity):
- MSK encryption at rest
- DynamoDB encryption with CMK
- S3 bucket encryption with CMK
- CloudWatch Logs encryption

**For production**:
```hcl
# MSK with encryption
resource "aws_msk_cluster" "example" {
  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk.arn
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }
}

# DynamoDB with CMK
resource "aws_dynamodb_table" "example" {
  server_side_encryption {
    enabled     = true
    kms_key_arn = aws_kms_key.dynamodb.arn
  }
}
```

### Data Retention and Deletion

**Current settings**:
- Kafka topics: 7 days retention (default)
- CloudWatch Logs: 7 days
- DynamoDB: 30-day TTL on audit records
- S3: 7-day lifecycle for old versions

**For production**:
- Define retention based on regulatory requirements
- Implement secure deletion procedures
- Add data classification
- Implement data loss prevention (DLP)

## API Security

### Current State

❌ **No authentication** on operator console API:
- Anyone with API URL can send kill commands
- No authorization checks
- No audit of who sent commands

### Production Requirements

**Authentication**:
- API keys (minimum)
- IAM authentication (better)
- OAuth 2.0 / OIDC (best)

**Authorization**:
- Role-based access control (RBAC)
- Attribute-based access control (ABAC)
- Separate read/write permissions

**Rate Limiting**:
```hcl
resource "aws_api_gateway_usage_plan" "example" {
  throttle_settings {
    burst_limit = 100
    rate_limit  = 50
  }
}
```

**Request Validation**:
- JSON schema validation
- Input sanitization
- Size limits

**Example secure API**:
```python
def lambda_handler(event, context):
    # 1. Authenticate
    user = authenticate_request(event)
    if not user:
        return {'statusCode': 401, 'body': 'Unauthorized'}
    
    # 2. Authorize
    if not user.has_permission('killswitch:write'):
        return {'statusCode': 403, 'body': 'Forbidden'}
    
    # 3. Validate input
    try:
        body = validate_json(event['body'], schema)
    except ValidationError:
        return {'statusCode': 400, 'body': 'Invalid input'}
    
    # 4. Audit
    audit_log(user, 'kill_command', body)
    
    # 5. Execute
    result = publish_command(body)
    return {'statusCode': 200, 'body': json.dumps(result)}
```

## Audit and Compliance

### Current Audit Trail

✅ **Implemented**:
- All kill commands logged to Kafka
- All routing decisions logged to audit topic
- Correlation IDs for traceability
- Immutable append-only log

❌ **Not implemented**:
- Cryptographic signatures on audit events
- Tamper-evident logging
- Long-term archival (>90 days)
- Audit log monitoring/alerting
- Compliance reporting

### SEC Rule 15c3-5 Compliance

**What the demo demonstrates**:
- ✅ Pre-trade risk controls (kill switch)
- ✅ Direct and exclusive control (operator console)
- ✅ Audit trail (Kafka + DynamoDB)
- ✅ Supervisory procedures (documented in repo)

**What's missing for compliance**:
- ❌ Regular testing and review procedures
- ❌ Formal risk management policies
- ❌ Compliance officer sign-off
- ❌ Regulatory reporting
- ❌ Disaster recovery testing
- ❌ Annual compliance certification

**For production**:
- Engage compliance team early
- Document all controls
- Implement regular testing
- Maintain audit trail for 7 years (SEC requirement)
- Implement change management procedures

## Secrets Management

### Current Approach

⚠️ **Minimal secrets** in demo:
- MSK bootstrap brokers in environment variables
- IAM roles for authentication (no keys)

### Production Approach

Use AWS Secrets Manager:
```python
import boto3

def get_secret(secret_name):
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

# In Lambda
kafka_config = get_secret('prod/kafka/config')
```

**Best practices**:
- Rotate secrets regularly
- Use IAM roles instead of keys where possible
- Never log secrets
- Use encryption for secrets at rest
- Implement secret scanning in CI/CD

## Incident Response

### Current Capabilities

✅ **Available**:
- CloudWatch Logs for debugging
- Audit trail for forensics
- Correlation IDs for tracing

❌ **Missing**:
- Automated alerting
- Incident response playbook
- Security monitoring (SIEM)
- Threat detection
- Automated remediation

### Production Incident Response

**Detection**:
- CloudWatch Alarms for anomalies
- GuardDuty for threat detection
- Security Hub for compliance
- Custom metrics for business logic

**Response**:
1. Detect anomaly
2. Alert on-call engineer
3. Isolate affected components
4. Investigate using audit trail
5. Remediate (e.g., trigger kill switch)
6. Document and review

**Example alarm**:
```hcl
resource "aws_cloudwatch_metric_alarm" "high_drop_rate" {
  alarm_name          = "high-order-drop-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DroppedOrders"
  namespace           = "StreamingRiskControls"
  period              = 60
  statistic           = "Sum"
  threshold           = 1000
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
```

## Dependency Security

### Current State

❌ **No dependency scanning**:
- Python packages not scanned for vulnerabilities
- No SBOM generated
- No license compliance checking

### Production Requirements

**Dependency scanning**:
```bash
# Scan Python dependencies
pip-audit

# Scan Docker images
trivy image <image-name>

# Scan Terraform
tfsec .
```

**Supply chain security**:
- Pin dependency versions
- Use private package repository
- Verify package signatures
- Regular dependency updates
- Automated vulnerability scanning in CI/CD

## Monitoring and Alerting

### Current Monitoring

✅ **Basic monitoring**:
- CloudWatch Logs
- CloudWatch Metrics
- CloudWatch Dashboard

❌ **Missing**:
- Security-specific monitoring
- Anomaly detection
- Threat intelligence
- User behavior analytics

### Production Monitoring

**Security metrics to track**:
- Failed authentication attempts
- Unusual API call patterns
- High kill switch activation rate
- Audit log gaps
- IAM policy changes
- Network traffic anomalies

**Tools**:
- AWS Security Hub
- Amazon GuardDuty
- AWS CloudTrail
- Third-party SIEM (Splunk, Datadog, etc.)

## Recommendations for Production

### Immediate (Before Production)

1. **Add API authentication** (IAM or API keys)
2. **Enable encryption at rest** (MSK, DynamoDB, S3)
3. **Implement secrets management** (Secrets Manager)
4. **Add input validation** (all APIs)
5. **Set up CloudWatch Alarms** (errors, high latency)

### Short-term (First Month)

1. **Security scanning** (dependencies, infrastructure)
2. **Penetration testing** (third-party)
3. **Compliance review** (legal/compliance team)
4. **Incident response plan** (documented procedures)
5. **Disaster recovery testing** (backup/restore)

### Long-term (Ongoing)

1. **Regular security audits** (quarterly)
2. **Compliance certifications** (SOC 2, ISO 27001)
3. **Security training** (for developers)
4. **Threat modeling** (updated regularly)
5. **Bug bounty program** (if public-facing)

## Summary

**Key takeaways**:
- This demo prioritizes education over security
- Many production security controls are omitted for simplicity
- Never use this code in production without significant hardening
- Engage security and compliance teams early
- Security is a journey, not a destination

**Remember**: The goal of this demo is to teach streaming architecture patterns, not to provide production-ready security. Always consult with security professionals before deploying trading systems.

## Resources

- [AWS Security Best Practices](https://aws.amazon.com/architecture/security-identity-compliance/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS AWS Foundations Benchmark](https://www.cisecurity.org/benchmark/amazon_web_services)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [SEC Cybersecurity Guidance](https://www.sec.gov/spotlight/cybersecurity)
