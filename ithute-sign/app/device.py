"""STU bridge device probe; no GUI dependencies so failures can be tested offline."""
from dataclasses import dataclass
from pathlib import Path
import subprocess

@dataclass(frozen=True)
class DeviceStatus:
    connected: bool
    message: str
    code: int


def probe_bridge(executable, *, timeout=12, runner=subprocess.run):
    """Probe actual Wacom USB enumeration, not merely presence of an executable.

    Bridge exit codes: 0 connected, 10 absent, 11 SDK/driver failure,
    12 incompatible invocation, 13 unexpected probe failure.
    """
    if executable is None or not Path(executable).is_file():
        return DeviceStatus(False, 'STU capture bridge is not installed.', 127)
    try:
        result = runner([str(executable), '--probe'], capture_output=True,
                        text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return DeviceStatus(False, 'STU device check timed out.', 124)
    except OSError as error:
        return DeviceStatus(False, f'Cannot start STU bridge: {error}', 126)
    explanation = (result.stdout or result.stderr or '').strip()
    explanations = {
        0: 'STU device detected. Ready to capture.',
        10: 'No Wacom STU USB device detected. Check cable and driver.',
        11: 'Wacom SDK or USB driver is unavailable.',
        12: 'The installed bridge does not support device checks. Rebuild it.',
        13: 'The STU device check failed unexpectedly.',
    }
    return DeviceStatus(result.returncode == 0,
                        explanation or explanations.get(result.returncode, 'STU check failed.'),
                        result.returncode)


def show_screen(executable, mode, *, timeout=15, runner=subprocess.run):
    """Ask the official STU SDK bridge to display a simple splash image."""
    if mode not in ('welcome', 'thanks'):
        raise ValueError('Unsupported STU display screen')
    if executable is None or not Path(executable).is_file():
        return DeviceStatus(False, 'STU bridge not installed.', 127)
    try:
        result = runner([str(executable), '--' + mode], capture_output=True,
                        text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return DeviceStatus(False, 'STU display request timed out.', 124)
    except OSError as error:
        return DeviceStatus(False, str(error), 126)
    message = (result.stdout or result.stderr or '').strip()
    return DeviceStatus(result.returncode == 0,
                        message or ('STU screen updated.' if result.returncode == 0 else 'STU display failed.'),
                        result.returncode)

def validate_signature_png(path):
    """Reject missing, empty, opaque, or blank bridge output before PDF insertion."""
    import struct
    target = Path(path)
    if not target.is_file() or target.stat().st_size < 80:
        raise ValueError("Signature image is missing or empty")
    data = target.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Signature output is not a PNG")
    if data[12:16] != b"IHDR":
        raise ValueError("Signature PNG is missing its image header")
    width, height, depth, color_type = struct.unpack(">IIBB", data[16:26])
    if not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise ValueError("Signature dimensions are invalid")
    if depth != 8 or color_type not in (4, 6):
        raise ValueError("Signature PNG must have an alpha channel")
    # Decode pixels rather than trusting the PNG header or file size.
    import fitz
    pixmap = fitz.Pixmap(str(target))
    if not pixmap.alpha:
        raise ValueError("Signature PNG has no alpha channel")
    alpha_bytes = pixmap.samples[pixmap.n - 1::pixmap.n]
    if not any(alpha_bytes):
        raise ValueError("Signature PNG contains no visible ink")
    if all(value == 255 for value in alpha_bytes):
        raise ValueError("Signature PNG has no transparent background")
    return target
