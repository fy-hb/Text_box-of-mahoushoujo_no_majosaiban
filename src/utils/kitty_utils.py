import sys
import os
from base64 import standard_b64encode
from io import BytesIO

try:
    from PIL import Image
except Exception as e:
    print("需要 Pillow (PIL)。请运行: pip install pillow", file=sys.stderr)
    raise SystemExit(1)


ESC = b'\x1b'   # escape
ST  = b'\x1b\\' # ESC backslash (string terminator used by the protocol)
CHUNK_SIZE = 4096  # 每片最大 4096 字节 (kitty 要求)


def serialize_gr_command(cmd_dict, payload=None):
    """
    将控制字段和 payload 序列化为一个完整的 kitty graphics escape 序列 (bytes)。
    格式: ESC _ G<control_data>;<payload>ESC\\
    """
    # control data: 逗号分隔的 key=value
    ctrl = ','.join(f'{k}={v}' for k, v in cmd_dict.items()).encode('ascii')
    parts = []
    parts.append(ESC + b'_G')
    parts.append(ctrl)
    if payload is not None:
        parts.append(b';')
        parts.append(payload)
    parts.append(ST)
    return b''.join(parts)


def write_chunked_to_stdout(data_bytes, **cmd):
    """
    将二进制图像数据 base64 编码后按 CHUNK_SIZE 分片发送到 stdout（终端）。
    cmd 中包含要发送的控制参数（例如 a='T', f=100 等）。
    """
    b64 = standard_b64encode(data_bytes)
    # 按 CHUNK_SIZE 分片。除了最后一片外，其他片的长度需为 4 的倍数 (base64 要求)
    pos = 0
    first = True
    # We will reuse cmd for the first chunk; subsequent chunks only have m=1 (or m=0 for last)
    while pos < len(b64):
        chunk = b64[pos:pos + CHUNK_SIZE]
        pos += CHUNK_SIZE
        more = pos < len(b64)
        # build command dict for this chunk
        if first:
            # full control fields only on first chunk
            cmd_chunk = dict(cmd)
            # m=1 表示还有后续片；最后一片 m=0
            cmd_chunk['m'] = 1 if more else 0
            payload = chunk
            first = False
        else:
            # subsequent chunks: only m (and optionally q) are required
            cmd_chunk = {'m': 1 if more else 0}
            payload = chunk

        seq = serialize_gr_command(cmd_chunk, payload=payload)
        # 写到 stdout 的二进制缓冲区并 flush
        sys.stdout.buffer.write(seq)
        sys.stdout.buffer.flush()


def image_to_png_bytes(path):
    """
    使用 Pillow 将任意图片格式转换为 PNG 并返回 PNG 的 bytes。
    如果输入已经是 PNG，也会重新编码（保证一致）。
    """
    with Image.open(path) as im:
        # 保证转换为 RGBA 或 RGB 根据需要；这里我们保存为 PNG（f=100）
        buf = BytesIO()
        # 若图片有透明度则保留
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and 'transparency' in im.info):
            im = im.convert("RGBA")
        else:
            im = im.convert("RGB")
        im.save(buf, format="PNG")
        return buf.getvalue()


def display_image(image_path):
    """
    Display an image in the terminal using the Kitty graphics protocol.
    """
    if not os.path.exists(image_path):
        return

    cmd = {'a': 'T', 'f': 100, 't': 'd'}
    png_bytes = image_to_png_bytes(image_path)
    write_chunked_to_stdout(png_bytes, **cmd)
