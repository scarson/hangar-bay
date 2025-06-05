# Hangar Bay - Security Specification

This document provides detailed security guidelines, standards, and technology-specific considerations for the Hangar Bay application. It complements the general Security section in the main `design-spec.txt`.

## 1. Cryptography

### 1.1. Encryption in Transit

*   **TLS Requirement:** All external network traffic to and from the Hangar Bay application (including user-to-frontend, frontend-to-backend, backend-to-ESI, backend-to-database if over a network) MUST be encrypted using Transport Layer Security (TLS) version 1.2 or, preferably, TLS 1.3.
*   **Cipher Suites:** Only cipher suites that provide Perfect Forward Secrecy (PFS) MUST be used. This ensures that if a long-term server private key is compromised, past session keys (and thus past encrypted traffic) cannot be decrypted.
    *   For TLS 1.3, PFS is inherent in all cipher suites.
    *   For TLS 1.2, prefer ECDHE-based cipher suites (e.g., `ECDHE-ECDSA-AES128-GCM-SHA256`, `ECDHE-RSA-AES256-GCM-SHA384`). Avoid static key exchange ciphers (non-PFS).
*   **Certificate Management:** Use strong, valid X.509 certificates from a reputable Certificate Authority (CA). Implement automated certificate renewal (e.g., via Let's Encrypt with Certbot or integrated cloud provider solutions).
*   **HTTP Strict Transport Security (HSTS):** Implement HSTS to instruct browsers to only connect to the application via HTTPS. Include `preload` directive for maximum effectiveness.

### 1.2. Encryption at Rest

*   **Principle of Data Minimization:** Do not store sensitive data if it is not absolutely necessary for core application functionality. You can't lose what you don't have.
*   **Scope:** This applies to data stored in the primary database (PostgreSQL), caching layer (Valkey, if persisting data or storing sensitive items), and any other persistent storage.
*   **Sensitive Data Requiring Encryption at Rest:**
    *   EVE SSO refresh tokens MUST be encrypted at rest in the database.
    *   User alert configurations or watchlist parameters, if they contain user-defined sensitive thresholds or notes, should be encrypted.
    *   Any other Personally Identifiable Information (PII) or user-specific sensitive data that must be stored.
*   **Encryption Methods:**
    *   **Database-Level Encryption:**
        *   Consider PostgreSQL's Transparent Data Encryption (TDE) capabilities if offered by the hosting environment, or full-disk encryption at the infrastructure level.
        *   Utilize PostgreSQL's `pgcrypto` extension for column-level encryption of specific sensitive fields (e.g., refresh tokens). This provides more granular control.
    *   **Application-Level Encryption:** For highly sensitive data, consider encrypting it within the application before storing it in the database. This requires careful key management.
    *   **Key Management:** Securely manage all encryption keys. Avoid hardcoding keys. Use a dedicated key management service (KMS) if available (e.g., AWS KMS, Azure Key Vault, HashiCorp Vault) or secure configuration management practices.
*   **Valkey Security:** While primarily a cache, if Valkey is configured for persistence or used to store sensitive session-like data, ensure its persistence files are protected by underlying file system permissions and disk encryption if possible. Valkey itself can be password protected.

### 1.3. Post-Quantum Cryptography (PQC) Aspiration

*   **Goal:** To enhance long-term data security against potential future threats from quantum computers.
*   **Strategy:** Monitor the standardization and maturation of NIST-approved Post-Quantum Cryptography algorithms (e.g., CRYSTALS-Kyber for Key Encapsulation Mechanisms - KEMs, CRYSTALS-Dilithium for digital signatures).
*   **Adoption Criteria:** Investigate and plan for the adoption of PQC for key exchange in TLS (e.g., via hybrid modes combining classical ECDHE with a PQC KEM) and potentially for other cryptographic functions (e.g., data-at-rest encryption, digital signatures on software updates) if applicable, under the following conditions:
    1.  Mature, well-vetted, and audited library support becomes available for the chosen technology stack (backend, frontend, web servers).
    2.  Integration does not introduce significant, unacceptable performance degradation.
    3.  Integration does not introduce undue complexity that could lead to implementation errors.
    4.  Industry best practices and standards for PQC deployment in web applications become clearer.
*   **Current Focus:** While PQC is an important future consideration, the immediate priority is the robust implementation of strong, classical cryptography (TLS 1.2/1.3 with PFS).

## 2. Authentication and Authorization

*(To be detailed: EVE SSO token handling, session management, API key security, role-based access control if applicable)*

## 3. Input Validation and Output Encoding

*(To be detailed: Specifics for chosen frameworks, prevention of XSS, SQLi, command injection, etc.)*

## 4. Application-Specific Vulnerabilities

*(To be detailed: e.g., ESI data manipulation risks, race conditions in contract aggregation, DoS/DDoS mitigation strategies)*

## 5. Dependency Management

*(To be detailed: Secure supply chain practices, vulnerability scanning)*

## 6. Logging and Monitoring

*(To be detailed: Security event logging, audit trails, intrusion detection/prevention)*

## 7. Infrastructure Security

*(To be detailed: Secure configuration of servers, databases, caching layers, firewalls)*
