#!/usr/bin/env python3
"""
AULA F87 PCAP Parser - Extracts and analyzes HID feature reports from pcapng files.

Supports macOS USBPcap captures with fragmented 20-byte packets that need reassembly.

Usage:
    python parse_captures.py <pcapng_file> [options]
    python parse_captures.py <file1> --diff <file2> [options]

Examples:
    python parse_captures.py startup.pcapng
    python parse_captures.py fixed_on.pcapng --diff respire.pcapng
    python parse_captures.py *.pcapng --summary
"""

import sys
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import pyshark
except ImportError:
    print("Error: pyshark not installed. Run: pip install pyshark")
    sys.exit(1)


@dataclass
class HIDFragment:
    """Represents a single 20-byte fragment."""

    packet_number: int
    timestamp: float
    direction: str
    endpoint: int
    sequence: int
    data: bytes


@dataclass
class HIDReport:
    """Represents a reassembled HID feature report."""

    start_packet: int
    end_packet: int
    timestamp: float
    direction: str
    endpoint: int
    data: bytes
    data_len: int

    def get_byte(self, offset: int) -> int:
        """Get byte at specific offset."""
        if offset < len(self.data):
            return self.data[offset]
        return 0


def parse_fragments(filepath: str) -> List[HIDFragment]:
    """Parse a pcapng file and extract 20-byte HID fragments."""
    fragments = []

    cap = pyshark.FileCapture(filepath)

    for packet in cap:
        try:
            # Check for DATA layer with usb_capdata
            if not hasattr(packet, "DATA"):
                continue

            data_layer = packet.DATA

            # Get the USB payload data
            if not hasattr(data_layer, "usb_capdata"):
                continue

            data_val = data_layer.usb_capdata
            if not data_val:
                continue

            # Convert LayerFieldsContainer to string and parse
            data_hex = str(data_val).replace(":", "").replace(" ", "")
            data = bytes.fromhex(data_hex)

            # We expect 20-byte fragments
            if len(data) != 20:
                continue

            # Get packet info
            usb_layer = packet.usb
            packet_num = int(packet.number)
            timestamp = float(packet.frame_info.time_relative)

            # Determine direction from USB addresses
            src = getattr(usb_layer, "src", "")
            if "host" in str(src).lower():
                direction = "host_to_device"
            else:
                direction = "device_to_host"

            # Get endpoint
            endpoint = int(getattr(usb_layer, "endpoint_address_number", "0"))

            # Extract sequence number from byte 3
            sequence = data[3] if len(data) > 3 else 0

            fragment = HIDFragment(
                packet_number=packet_num,
                timestamp=timestamp,
                direction=direction,
                endpoint=endpoint,
                sequence=sequence,
                data=data,
            )

            fragments.append(fragment)

        except Exception as e:
            # Skip packets that don't have the expected structure
            continue

    cap.close()
    return fragments


def reassemble_reports(fragments: List[HIDFragment]) -> List[HIDReport]:
    """Reassemble 20-byte fragments into full 520-byte HID reports."""
    reports = []

    # Group fragments by direction and endpoint
    # A complete report consists of 26 fragments (0x00 to 0x19 = 26, 26*20=520 bytes)
    current_fragments: Dict[Tuple[str, int], List[HIDFragment]] = defaultdict(list)

    for frag in sorted(fragments, key=lambda f: f.packet_number):
        key = (frag.direction, frag.endpoint)

        # Check if we should start a new report
        if frag.sequence == 0 and current_fragments[key]:
            # Reassemble the previous report
            frags = current_fragments[key]
            if len(frags) >= 2:  # Need at least a couple fragments
                full_data = b"".join(f.data for f in frags)
                reports.append(
                    HIDReport(
                        start_packet=frags[0].packet_number,
                        end_packet=frags[-1].packet_number,
                        timestamp=frags[0].timestamp,
                        direction=frags[0].direction,
                        endpoint=frags[0].endpoint,
                        data=full_data,
                        data_len=len(full_data),
                    )
                )
            current_fragments[key] = []

        current_fragments[key].append(frag)

        # Check if we have a complete 520-byte report
        if len(current_fragments[key]) >= 26:
            frags = current_fragments[key]
            full_data = b"".join(f.data for f in frags)
            reports.append(
                HIDReport(
                    start_packet=frags[0].packet_number,
                    end_packet=frags[-1].packet_number,
                    timestamp=frags[0].timestamp,
                    direction=frags[0].direction,
                    endpoint=frags[0].endpoint,
                    data=full_data,
                    data_len=len(full_data),
                )
            )
            current_fragments[key] = []

    # Handle any remaining fragments
    for key, frags in current_fragments.items():
        if len(frags) >= 2:
            full_data = b"".join(f.data for f in frags)
            reports.append(
                HIDReport(
                    start_packet=frags[0].packet_number,
                    end_packet=frags[-1].packet_number,
                    timestamp=frags[0].timestamp,
                    direction=frags[0].direction,
                    endpoint=frags[0].endpoint,
                    data=full_data,
                    data_len=len(full_data),
                )
            )

    return reports


def parse_pcapng(filepath: str) -> Tuple[List[HIDFragment], List[HIDReport]]:
    """Parse a pcapng file and return both fragments and reassembled reports."""
    fragments = parse_fragments(filepath)
    reports = reassemble_reports(fragments)
    return fragments, reports


def format_hex_dump(data: bytes, offset: int = 0, width: int = 16) -> str:
    """Format bytes as a hex dump with offsets."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset + i:04x}:  {hex_part:<{width * 3}}  {ascii_part}")
    return "\n".join(lines)


def label_byte_offset(offset: int) -> str:
    """Return a label for known byte offsets based on protocol documentation."""
    if offset == 0:
        return "report_id"
    elif offset == 1:
        return "cmd_byte1"
    elif offset == 2:
        return "cmd_byte2"
    elif offset == 3:
        return "seq_num"
    elif offset == 4:
        return "cmd_type"
    elif offset == 5:
        return "subcmd"
    elif offset == 13:
        return "model_id"
    elif offset >= 8 and offset < 520:
        return "data/payload"
    return ""


def annotate_hex_dump(data: bytes, highlight_offsets: Optional[Set[int]] = None) -> str:
    """Format hex dump with annotations for known fields."""
    lines = []
    width = 16
    highlight_offsets = highlight_offsets or set()

    for i in range(0, len(data), width):
        chunk = data[i : i + width]
        hex_bytes = []
        annotations = []

        for j, b in enumerate(chunk):
            offset = i + j
            if offset in highlight_offsets:
                hex_bytes.append(f"**{b:02x}**")
            else:
                hex_bytes.append(f"{b:02x}")
            label = label_byte_offset(offset)
            if label:
                annotations.append(f"[{offset:03d}:{label}]")

        hex_str = " ".join(hex_bytes)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)

        lines.append(f"{i:04x}:  {hex_str:<{width * 4}}  {ascii_str}")
        if annotations:
            lines.append(f"       {'  '.join(annotations)}")

    return "\n".join(lines)


def print_report(report: HIDReport, verbose: bool = False):
    """Print a single HID report."""
    direction_str = (
        "host→device" if report.direction == "host_to_device" else "device→host"
    )

    print(f"\n{'=' * 80}")
    print(
        f"Report: Packets #{report.start_packet}-{report.end_packet} | {direction_str}"
    )
    print(
        f"Time: {report.timestamp:.6f}s | Endpoint: {report.endpoint} | Length: {report.data_len} bytes"
    )
    print(f"{'=' * 80}")

    if report.data:
        print(format_hex_dump(report.data[: min(520, len(report.data))]))
    else:
        print("(no data)")


def compare_reports(
    reports1: List[HIDReport],
    reports2: List[HIDReport],
    label1: str = "File1",
    label2: str = "File2",
) -> List[Dict]:
    """Compare two sets of reports and find differences."""
    differences = []

    # Get large reports (commands from host, echoed by device)
    # On macOS USBPcap, host commands appear as device responses
    cmd_reports1 = [r for r in reports1 if r.data_len >= 100]
    cmd_reports2 = [r for r in reports2 if r.data_len >= 100]

    if not cmd_reports1 or not cmd_reports2:
        print(f"Warning: Insufficient command reports for comparison")
        print(f"  {label1}: {len(cmd_reports1)} command reports")
        print(f"  {label2}: {len(cmd_reports2)} command reports")
        return differences

    # Compare reports with matching sizes
    # Find reports that exist in both files with the same size
    differences = []
    for r1 in cmd_reports1:
        for r2 in cmd_reports2:
            if r1.data_len == r2.data_len:
                # Compare these reports
                diffs = compare_data(r1.data, r2.data, r1.data_len)
                if diffs:
                    differences.extend(diffs)
                break  # Only compare first matching size

    return differences


def compare_data(data1: bytes, data2: bytes, data_len: int) -> List[Dict]:
    """Compare two byte arrays and return differences."""
    differences = []
    min_len = min(len(data1), len(data2), data_len)

    # Compare byte by byte
    min_len = min(len(data1), len(data2))
    for offset in range(min_len):
        if data1[offset] != data2[offset]:
            diff = {
                "byte_offset": offset,
                "old_value": data1[offset],
                "new_value": data2[offset],
                "old_hex": f"{data1[offset]:02x}",
                "new_hex": f"{data2[offset]:02x}",
                "label": label_byte_offset(offset),
            }
            differences.append(diff)

    return differences


def print_diff_table(differences: List[Dict], label1: str, label2: str):
    """Print a formatted table of byte differences."""
    if not differences:
        print("\nNo differences found between captures.")
        return

    print(f"\n{'=' * 80}")
    print(f"DIFFERENCE ANALYSIS: {label1} vs {label2}")
    print(f"{'=' * 80}")
    print(
        f"{'Byte Offset':<12} {'Field':<15} {'Old Value':<12} {'New Value':<12} {'Change'}"
    )
    print(f"{'-' * 80}")

    for diff in differences:
        offset = diff["byte_offset"]
        label = diff["label"] or "unknown"
        old_val = diff["old_hex"]
        new_val = diff["new_hex"]

        # Heuristic: identify what changed
        if offset < 8:
            what = "header"
        elif offset == 13:
            what = "model_id"
        elif offset >= 8 and offset < 100:
            what = "effect_params"
        else:
            what = "rgb_data"

        print(
            f"{offset:<12} {what:<15} 0x{old_val:<10} 0x{new_val:<10} {old_val} -> {new_val}"
        )

    print(f"{'-' * 80}")
    print(f"Total differences: {len(differences)}")


def analyze_capture(filepath: str) -> Tuple[List[HIDFragment], List[HIDReport], Dict]:
    """Analyze a capture file and return fragments, reports, and summary."""
    print(f"\nAnalyzing: {filepath}")
    print("=" * 80)

    fragments, reports = parse_pcapng(filepath)

    if not fragments:
        print("No HID fragments found in capture.")
        return fragments, reports, {}

    # Summary statistics
    host_to_dev = [r for r in reports if r.direction == "host_to_device"]
    dev_to_host = [r for r in reports if r.direction == "device_to_host"]
    large_reports = [r for r in reports if r.data_len >= 520]

    summary = {
        "file": filepath,
        "fragments": len(fragments),
        "reports": len(reports),
        "host_to_device": len(host_to_dev),
        "device_to_host": len(dev_to_host),
        "large_reports": len(large_reports),
    }

    print(f"USB HID Fragments: {len(fragments)}")
    print(f"Reassembled Reports: {len(reports)}")
    print(f"  Host→Device: {len(host_to_dev)}")
    print(f"  Device→Host: {len(dev_to_host)}")
    print(f"  Full-size (≥520 bytes): {len(large_reports)}")

    return fragments, reports, summary


def main():
    parser = argparse.ArgumentParser(
        description="Parse USB HID feature reports from pcapng captures (macOS USBPcap format)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s capture.pcapng                 # Analyze single capture
  %(prog)s cap1.pcapng --diff cap2.pcapng   # Compare two captures
  %(prog)s *.pcapng --summary             # Summarize all captures
  %(prog)s capture.pcapng --verbose       # Show annotated hex dump
        """,
    )

    parser.add_argument("files", nargs="+", help="pcapng file(s) to analyze")
    parser.add_argument(
        "--diff", metavar="FILE", help="Compare with second capture file"
    )
    parser.add_argument("--summary", action="store_true", help="Print summary only")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed hex dumps with annotations",
    )
    parser.add_argument(
        "--fragments", action="store_true", help="Show individual 20-byte fragments"
    )
    parser.add_argument(
        "--filter-size", type=int, default=0, help="Filter reports of minimum size"
    )

    args = parser.parse_args()

    if args.diff and len(args.files) != 1:
        parser.error("--diff requires exactly one file as first argument")

    # Analyze files
    all_reports = {}
    all_summaries = []

    for filepath in args.files:
        if not Path(filepath).exists():
            print(f"Error: File not found: {filepath}")
            continue

        fragments, reports, summary = analyze_capture(filepath)
        all_reports[filepath] = reports
        all_summaries.append(summary)

        if not args.summary and not args.diff:
            # Print detailed reports
            if args.fragments:
                print(f"\n--- 20-byte Fragments ---")
                for frag in fragments[:20]:  # Limit to first 20
                    print(
                        f"Pkt #{frag.packet_number:3} | Seq {frag.sequence:02x} | {frag.direction:15} | "
                        f"{' '.join(f'{b:02x}' for b in frag.data)}"
                    )

            for report in reports:
                if report.data_len >= args.filter_size:
                    print_report(report, verbose=args.verbose)

    # Print summary table if multiple files or --summary flag
    if len(args.files) > 1 or args.summary:
        print(f"\n\n{'=' * 80}")
        print("CAPTURE SUMMARY")
        print(f"{'=' * 80}")
        print(f"{'File':<45} {'Frags':<8} {'Reports':<8} {'Host→Dev':<10} {'Large':<8}")
        print(f"{'-' * 80}")
        for s in all_summaries:
            filename = Path(s["file"]).name[:43]
            print(
                f"{filename:<45} {s['fragments']:<8} {s['reports']:<8} "
                f"{s['host_to_device']:<10} {s['large_reports']:<8}"
            )

    # Diff mode
    if args.diff:
        file1 = args.files[0]
        file2 = args.diff

        if file2 not in all_reports:
            if Path(file2).exists():
                _, reports2, _ = analyze_capture(file2)
            else:
                print(f"Error: File not found: {file2}")
                sys.exit(1)
        else:
            reports2 = all_reports[file2]

        reports1 = all_reports[file1]

        label1 = Path(file1).stem
        label2 = Path(file2).stem

        differences = compare_reports(reports1, reports2, label1, label2)
        print_diff_table(differences, label1, label2)

    # Compare all pairs if exactly 2 files provided without --diff
    elif len(args.files) == 2 and not args.diff:
        file1, file2 = args.files[0], args.files[1]
        label1 = Path(file1).stem
        label2 = Path(file2).stem

        differences = compare_reports(
            all_reports[file1], all_reports[file2], label1, label2
        )
        print_diff_table(differences, label1, label2)


if __name__ == "__main__":
    main()
