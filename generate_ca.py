"""Generate a new self-signed Root CA certificate for LocketGold (Mavrixdev)."""
import base64
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# 1. Generate RSA 2048 private key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# 2. Build the self-signed CA certificate
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COMMON_NAME, "Mavrixdev-LocketGold-CA"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Mavrixdev"),
    x509.NameAttribute(NameOID.COUNTRY_NAME, "VN"),
])

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.now(timezone.utc))
    .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))  # 10 years
    .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    .add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False
    )
    .add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
        critical=False,
    )
    .sign(key, hashes.SHA256())
)

# 3. Save private key (PEM) — keep this SECRET, used on your server
key_pem = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)
with open("Mavrixdev-LocketGold-CA.key", "wb") as f:
    f.write(key_pem)

# 4. Save certificate (PEM) — this gets embedded in the mobileconfig
cert_pem = cert.public_bytes(serialization.Encoding.PEM)
with open("Mavrixdev-LocketGold-CA.crt", "wb") as f:
    f.write(cert_pem)

# 5. Output the base64 string for embedding in .mobileconfig <data> tag
cert_b64 = base64.b64encode(cert_pem).decode("ascii")
print("=== BASE64 for mobileconfig <data> tag ===")
print(cert_b64)
print()
print(f"Certificate CN: {cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value}")
print(f"Organization:   {cert.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value}")
print(f"Valid from:     {cert.not_valid_before_utc}")
print(f"Valid until:    {cert.not_valid_after_utc}")
print(f"Serial:         {cert.serial_number}")
print()
print("Files created:")
print("  - Mavrixdev-LocketGold-CA.key  (PRIVATE KEY — keep secret, use on server)")
print("  - Mavrixdev-LocketGold-CA.crt  (PUBLIC CERT — embed in mobileconfig)")
