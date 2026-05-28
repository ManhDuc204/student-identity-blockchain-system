import os
import qrcode


def generate_student_qr(student_id: str, qr_dir: str) -> str:
    os.makedirs(qr_dir, exist_ok=True)
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    # QR encodes a URL to verify
    verify_url = f"/verify?student_id={student_id}"
    qr.add_data(verify_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    filename = f"student_{student_id}.png".replace(" ", "_")
    path = os.path.join(qr_dir, filename)
    img.save(path)
    return filename

