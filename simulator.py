import random
import streamlit as st
from collections import deque
from enum import Enum
from typing import Dict, List, Optional, Tuple
import time
import datetime
import pandas as pd
import numpy as np
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ------------------------------
# CONFIGURATION
# ------------------------------

COLOR_DISTRIBUTION: Dict[str, float] = {
    "C1": 0.20, "C2": 0.25, "C3": 0.12, "C4": 0.20, "C5": 0.03,
    "C6": 0.02, "C7": 0.02, "C8": 0.02, "C9": 0.10, "C10": 0.02, "C11": 0.02, "C12": 0.01
}

BUFFER_CONFIG: Dict[str, Dict[str, object]] = {
    "L1": {"capacity": 14, "oven": "O1"},
    "L2": {"capacity": 14, "oven": "O1"},
    "L3": {"capacity": 14, "oven": "O1"},
    "L4": {"capacity": 14, "oven": "O1"},  # Changed from O2 to O1
    "L5": {"capacity": 16, "oven": "O2"},
    "L6": {"capacity": 16, "oven": "O2"},
    "L7": {"capacity": 16, "oven": "O2"},
    "L8": {"capacity": 16, "oven": "O2"},
    "L9": {"capacity": 16, "oven": "O2"},
}

# Updated buffer allocations
O1_BUFFERS = ["L1", "L2", "L3", "L4"]  # Now includes L4
O2_BUFFERS = ["L5", "L6", "L7", "L8", "L9"]  # Now only L5-L9
ALL_COLORS = list(COLOR_DISTRIBUTION.keys())

# Color mapping for UI
COLOR_MAP = {
    "C1": "#432323", "C2": "#D97D55", "C3": "#696FC7", "C4": "#F2AEBB",
    "C5": "#134686", "C6": "#feb21a", "C7": "#3a6f43", "C8": "#08cb00",
    "C9": "#f5d2d2", "C10": "#bde3c3", "C11": "#00caff", "C12": "#00ffde"
}

# Time configuration
PROCESSING_TIME_PER_VEHICLE = 1  # 1 second base processing time per vehicle
PENALTY_TIME_O1_L5_L9 = 1  # 1 second penalty when O1 uses L5-L9
PENALTY_TIME_COLOR_CHANGE = 1  # 1 second penalty for color change on conveyor

# ------------------------------
# HELPERS
# ------------------------------

def generate_vehicle_color() -> str:
    r = random.random()
    cum = 0.0
    for color, p in COLOR_DISTRIBUTION.items():
        cum += p
        if r <= cum:
            return color
    return "C1"


class OvenType(Enum):
    O1 = "O1"
    O2 = "O2"


class VehicleBody:
    def __init__(self, body_id: int, color: str, source_oven: OvenType):
        self.body_id = body_id
        self.color = color
        self.source_oven = source_oven

    def __repr__(self):
        return f"Body({self.body_id}, {self.color}, {self.source_oven.value})"


class BufferLine:
    def __init__(self, line_id: str, capacity: int):
        self.line_id = line_id
        self.capacity = capacity
        self.queue = deque()
        self.is_available_input = True
        self.is_available_output = True

    def is_full(self) -> bool:
        return len(self.queue) >= self.capacity

    def is_empty(self) -> bool:
        return len(self.queue) == 0

    def add_body(self, body: VehicleBody) -> bool:
        if not self.is_available_input or len(self.queue) >= self.capacity:
            return False
        self.queue.append(body)
        return True

    def remove_body(self) -> Optional[VehicleBody]:
        if not self.is_available_output or len(self.queue) == 0:
            return None
        return self.queue.popleft()

    def peek_head(self) -> Optional[VehicleBody]:
        if len(self.queue) == 0:
            return None
        return self.queue[0]

    def get_filled_length(self) -> int:
        return len(self.queue)

    def get_remaining_capacity(self) -> int:
        return self.capacity - len(self.queue)


# ------------------------------
# SIMPLE ROUND-ROBIN CONVEYOR SYSTEM
# ------------------------------

class SimpleRoundRobinConveyorSystem:
    def __init__(self):
        self.buffer_lines: Dict[str, BufferLine] = {}
        for i in range(1, 5):  # L1-L4 for O1
            self.buffer_lines[f"L{i}"] = BufferLine(f"L{i}", 14)
        for i in range(5, 10):  # L5-L9 for O2
            self.buffer_lines[f"L{i}"] = BufferLine(f"L{i}", 16)

        self.main_conveyor_last_color: Optional[str] = None
        self.color_changeovers = 0
        self.total_processed = 0
        self.body_counter = 0
        self.penaltyCount = 0
        self.o2Stopped = False
        self.main_conveyor_sequence = []
        
        # Round-robin counters
        self.o1_buffer_counter = 0
        self.o2_buffer_counter = 0
        self.conveyor_buffer_counter = 0
        
        # Time tracking
        self.total_penalty_time = 0
        self.jph = 0.0
        self.start_time = time.time()

    def is_full(self, buffer_id: str) -> bool:
        return self.buffer_lines[buffer_id].is_full()

    def is_empty(self, buffer_id: str) -> bool:
        return self.buffer_lines[buffer_id].is_empty()

    def get_space(self, buffer_id: str) -> int:
        return self.buffer_lines[buffer_id].get_remaining_capacity()

    def place_vehicle(self, buffer_id: str, body: VehicleBody) -> bool:
        return self.buffer_lines[buffer_id].add_body(body)

    def simple_round_robin_placement(self, buffer_ids: List[str], body: VehicleBody) -> Optional[str]:
        """Simple round-robin placement without considering colors"""
        start_index = self.o1_buffer_counter if buffer_ids == O1_BUFFERS else self.o2_buffer_counter
        counter = start_index
        
        # Try all buffers in round-robin order
        for _ in range(len(buffer_ids)):
            buffer_id = buffer_ids[counter]
            if not self.is_full(buffer_id):
                # Update counter for next placement
                if buffer_ids == O1_BUFFERS:
                    self.o1_buffer_counter = (counter + 1) % len(buffer_ids)
                else:
                    self.o2_buffer_counter = (counter + 1) % len(buffer_ids)
                return buffer_id
            counter = (counter + 1) % len(buffer_ids)
        
        # All buffers are full
        return None

    def place_for_o1(self, body: VehicleBody) -> Tuple[Optional[str], bool, bool]:
        """Place O1 vehicle using simple round-robin"""
        self.o2Stopped = False
        penalty_applied = False
        
        # First try O1 buffers (L1-L4)
        buffer_id = self.simple_round_robin_placement(O1_BUFFERS, body)
        if buffer_id:
            self.place_vehicle(buffer_id, body)
            return buffer_id, False, penalty_applied
        
        # If O1 buffers are full, try O2 buffers (L5-L9) with penalty
        buffer_id = self.simple_round_robin_placement(O2_BUFFERS, body)
        if buffer_id:
            self.penaltyCount += 1
            self.o2Stopped = True
            self.place_vehicle(buffer_id, body)
            # Apply penalty for O1 using L5-L9
            self.total_penalty_time += PENALTY_TIME_O1_L5_L9
            penalty_applied = True
            return buffer_id, True, penalty_applied
        
        return None, False, penalty_applied

    def place_for_o2(self, body: VehicleBody) -> Optional[str]:
        """Place O2 vehicle using simple round-robin"""
        if self.o2Stopped:
            return None
        
        buffer_id = self.simple_round_robin_placement(O2_BUFFERS, body)
        if buffer_id:
            self.place_vehicle(buffer_id, body)
            return buffer_id
        
        return None

    def simple_round_robin_extraction(self) -> Optional[str]:
        """Simple round-robin extraction from all buffers"""
        start_index = self.conveyor_buffer_counter
        all_buffers = list(self.buffer_lines.keys())
        counter = start_index
        
        # Try all buffers in round-robin order
        for _ in range(len(all_buffers)):
            buffer_id = all_buffers[counter]
            if not self.is_empty(buffer_id):
                # Update counter for next extraction
                self.conveyor_buffer_counter = (counter + 1) % len(all_buffers)
                return buffer_id
            counter = (counter + 1) % len(all_buffers)
        
        # All buffers are empty
        return None

    def select_buffer_for_main_conveyor(self) -> Optional[str]:
        """Select buffer for main conveyor using simple round-robin"""
        return self.simple_round_robin_extraction()

    def update_jph(self):
        """JPH calculation: vehicles / (vehicles * 1s + penalty_time) × 3600"""
        base_processing_time = self.total_processed * PROCESSING_TIME_PER_VEHICLE
        total_effective_time = base_processing_time + self.total_penalty_time
        
        if total_effective_time > 0:
            self.jph = (self.total_processed / total_effective_time) * 3600
        else:
            self.jph = 0

    def get_time_breakdown(self) -> Dict[str, float]:
        """Get time breakdown for display"""
        base_time = self.total_processed * PROCESSING_TIME_PER_VEHICLE
        total_time = base_time + self.total_penalty_time
        return {
            'base_processing_time': base_time,
            'penalty_time': self.total_penalty_time,
            'total_effective_time': total_time
        }


# ------------------------------
# OPTIMIZED CONVEYOR SYSTEM (with temp buffer)
# ------------------------------

class ConveyorSystem:
    def __init__(self):
        self.buffer_lines: Dict[str, BufferLine] = {}
        for i in range(1, 5):  # L1-L4 for O1
            self.buffer_lines[f"L{i}"] = BufferLine(f"L{i}", 14)
        for i in range(5, 10):  # L5-L9 for O2
            self.buffer_lines[f"L{i}"] = BufferLine(f"L{i}", 16)

        self.main_conveyor_last_color: Optional[str] = None
        self.color_changeovers = 0
        self.total_processed = 0
        self.body_counter = 0
        self.penaltyCount = 0
        self.o2Stopped = False
        self.main_conveyor_sequence = []
        self.o2_temp_buffer: deque = deque()  # Temporary buffer for O2 when blocked
        
        # Time tracking
        self.total_penalty_time = 0
        self.jph = 0.0
        self.start_time = time.time()

    def get_o1_lines(self) -> List[str]:
        return O1_BUFFERS

    def get_o2_lines(self) -> List[str]:
        return O2_BUFFERS

    def is_full(self, buffer_id: str) -> bool:
        return self.buffer_lines[buffer_id].is_full()

    def is_empty(self, buffer_id: str) -> bool:
        return self.buffer_lines[buffer_id].is_empty()

    def get_front_color(self, buffer_id: str) -> Optional[str]:
        head = self.buffer_lines[buffer_id].peek_head()
        return head.color if head else None

    def get_rear_color(self, buffer_id: str) -> Optional[str]:
        buf = self.buffer_lines[buffer_id].queue
        return buf[-1].color if buf else None

    def get_rear_color_group_size(self, buffer_id: str) -> int:
        buf = self.buffer_lines[buffer_id].queue
        if not buf:
            return 0
        rear = buf[-1].color
        count = 0
        for body in reversed(buf):
            if body.color == rear:
                count += 1
            else:
                break
        return count

    def is_fully_of_color(self, buffer_id: str, color: str) -> bool:
        buf = self.buffer_lines[buffer_id].queue
        return len(buf) > 0 and all(body.color == color for body in buf)

    def ends_with_color(self, buffer_id: str, color: str) -> bool:
        rear = self.get_rear_color(buffer_id)
        return rear == color

    def get_space(self, buffer_id: str) -> int:
        return self.buffer_lines[buffer_id].get_remaining_capacity()

    def place_vehicle(self, buffer_id: str, body: VehicleBody) -> bool:
        return self.buffer_lines[buffer_id].add_body(body)

    def f1(self, buffer_ids: List[str], color: str) -> Optional[str]:
        for bid in buffer_ids:
            buf = self.buffer_lines[bid]
            if not buf.is_available_input:
                continue
            if self.is_fully_of_color(bid, color) and not self.is_full(bid):
                return bid
        for bid in buffer_ids:
            buf = self.buffer_lines[bid]
            if self.ends_with_color(bid, color) and not self.is_full(bid):
                return bid
        for bid in buffer_ids:
            buf = self.buffer_lines[bid]
            if not buf.is_available_input:
                continue
            if self.is_empty(bid):
                return bid
        return None

    def find_buffer_to_break(self, buffer_ids: List[str], color: str) -> Optional[str]:
        candidates = []
        for bid in buffer_ids:
            buf = self.buffer_lines[bid]
            # Skip buffers closed for input or already full
            if not buf.is_available_input or buf.is_full():
                continue
            
            group_sz = self.get_rear_color_group_size(bid)
            space = self.get_space(bid)
            candidates.append((bid, group_sz, space))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x[1], -x[2]))
        return candidates[0][0]

    def place_for_o1(self, body: VehicleBody) -> Tuple[Optional[str], bool, bool]:
        self.o2Stopped = False
        penalty_applied = False
        
        # First try O1 buffers (L1-L4)
        bid = self.f1(O1_BUFFERS, body.color)
        if bid:
            self.place_vehicle(bid, body)
            return bid, False, penalty_applied

        # If O1 buffers are full, try O2 buffers (L5-L9) with penalty
        bid = self.f1(O2_BUFFERS, body.color)
        if bid:
            self.penaltyCount += 1
            self.o2Stopped = True
            self.place_vehicle(bid, body)
            # Apply penalty for O1 using L5-L9
            self.total_penalty_time += PENALTY_TIME_O1_L5_L9
            penalty_applied = True
            return bid, True, penalty_applied

        bid = self.find_buffer_to_break(O1_BUFFERS, body.color)
        if bid:
            self.place_vehicle(bid, body)
            return bid, False, penalty_applied

        bid = self.find_buffer_to_break(O2_BUFFERS, body.color)
        if bid:
            self.penaltyCount += 1
            self.o2Stopped = True
            self.place_vehicle(bid, body)
            # Apply penalty for O1 using L5-L9
            self.total_penalty_time += PENALTY_TIME_O1_L5_L9
            penalty_applied = True
            return bid, True, penalty_applied

        return None, False, penalty_applied

    def place_for_o2(self, body: VehicleBody) -> Optional[str]:
        # If O2 is blocked OR temp buffer has vehicles, add the new vehicle to temporary buffer
        if self.o2Stopped or len(self.o2_temp_buffer) > 0:
            self.o2_temp_buffer.append(body)
            return "TMP_BUFFER"
        
        # Only process normally if temp buffer is empty and O2 is not blocked
        bid = self.f1(O2_BUFFERS, body.color)
        if bid:
            self.place_vehicle(bid, body)
            return bid
        bid = self.find_buffer_to_break(O2_BUFFERS, body.color)
        if bid:
            self.place_vehicle(bid, body)
            return bid
        return None
    
    def process_o2_temp_buffer(self) -> Optional[Tuple[VehicleBody, str]]:
        """Process vehicles from O2 temporary buffer when O2 is unblocked"""
        if not self.o2_temp_buffer or self.o2Stopped:
            return None
        
        body = self.o2_temp_buffer.popleft()
        bid = self.f1(O2_BUFFERS, body.color)
        if bid:
            self.place_vehicle(bid, body)
            return (body, bid)
        bid = self.find_buffer_to_break(O2_BUFFERS, body.color)
        if bid:
            self.place_vehicle(bid, body)
            return (body, bid)
        # If still can't place, put it back
        self.o2_temp_buffer.appendleft(body)
        return None

    def f1_find_max_connected_color(self) -> Optional[str]:
        color_counts: Dict[str, int] = {}
        buffer_meta = {}
        for line_id, buffer_line in self.buffer_lines.items():
            if buffer_line.is_empty() or not buffer_line.is_available_output:
                continue
            head_color = buffer_line.peek_head().color
            count = 0
            for body in buffer_line.queue:
                if body.color == head_color:
                    count += 1
                else:
                    break
            color_counts[head_color] = max(color_counts.get(head_color, 0), count)
            remaining_capacity = buffer_line.get_remaining_capacity()
            if head_color not in buffer_meta or count > buffer_meta[head_color][1]:
                buffer_meta[head_color] = (line_id, count, remaining_capacity)
        if not color_counts:
            return None
        max_freq = max(color_counts.values())
        candidates = [c for c in color_counts if color_counts[c] == max_freq]
        if len(candidates) == 1:
            return candidates[0]
        best_color = None
        best_tuple = None
        for color in candidates:
            line_id, connected_count, remaining_capacity = buffer_meta[color]
            current_tuple = (remaining_capacity, -connected_count, line_id)
            if best_tuple is None or current_tuple < best_tuple:
                best_tuple = current_tuple
                best_color = color
        return best_color

    def f2_choose_buffer_for_color(self, target_color: str) -> Optional[str]:
        candidate_lines = []
        for line_id, buffer_line in self.buffer_lines.items():
            if buffer_line.is_empty() or not buffer_line.is_available_output:
                continue
            head_body = buffer_line.peek_head()
            if head_body and head_body.color == target_color:
                remaining_capacity = buffer_line.get_remaining_capacity()
                candidate_lines.append((line_id, remaining_capacity))
        if not candidate_lines:
            return None
        candidate_lines.sort(key=lambda x: x[1])
        return candidate_lines[0][0]

    def are_all_o2_buffers_full(self) -> bool:
        for line_id in O2_BUFFERS:
            buf = self.buffer_lines[line_id]
            if buf.is_available_input and not buf.is_full():
                return False
        return True

    def select_buffer_for_main_conveyor(self) -> Optional[str]:
        if self.are_all_o2_buffers_full():
            max_color = self.f1_find_max_connected_color()
            if max_color:
                return self.f2_choose_buffer_for_color(max_color)
            return None
        if self.main_conveyor_last_color:
            matching_buffers = []
            for line_id, buffer_line in self.buffer_lines.items():
                if buffer_line.is_empty() or not buffer_line.is_available_output:
                    continue
                head_body = buffer_line.peek_head()
                if head_body and head_body.color == self.main_conveyor_last_color:
                    remaining_capacity = buffer_line.get_remaining_capacity()
                    matching_buffers.append((line_id, remaining_capacity))
            if len(matching_buffers) == 1:
                return matching_buffers[0][0]
            elif len(matching_buffers) > 1:
                matching_buffers.sort(key=lambda x: x[1])
                return matching_buffers[0][0]
        max_color = self.f1_find_max_connected_color()
        if max_color:
            return self.f2_choose_buffer_for_color(max_color)
        return None

    def update_jph(self):
        """JPH calculation: vehicles / (vehicles * 1s + penalty_time) × 3600"""
        base_processing_time = self.total_processed * PROCESSING_TIME_PER_VEHICLE
        total_effective_time = base_processing_time + self.total_penalty_time
        
        if total_effective_time > 0:
            self.jph = (self.total_processed / total_effective_time) * 3600
        else:
            self.jph = 0

    def get_time_breakdown(self) -> Dict[str, float]:
        """Get time breakdown for display"""
        base_time = self.total_processed * PROCESSING_TIME_PER_VEHICLE
        total_time = base_time + self.total_penalty_time
        return {
            'base_processing_time': base_time,
            'penalty_time': self.total_penalty_time,
            'total_effective_time': total_time
        }


# ------------------------------
# REPORT GENERATION FUNCTIONS
# ------------------------------

def format_color_distribution(color_counts, total):
    """Format color distribution statistics"""
    if not color_counts:
        return "   No data available"
    
    result = ""
    for color in sorted(color_counts.keys()):
        count = color_counts[color]
        percentage = (count / total * 100) if total > 0 else 0
        bar = '█' * int(percentage / 2)
        result += f"   {color:>4}: {count:>4} vehicles ({percentage:>5.2f}%) {bar}\n"
    
    return result.strip()


def format_buffer_stats(buffer_stats):
    """Format buffer statistics"""
    result = ""
    for line_id in sorted(buffer_stats.keys()):
        stats = buffer_stats[line_id]
        capacity = stats['capacity']
        filled = stats['filled']
        utilization = stats['utilization']
        bar = '█' * int(utilization / 5)
        result += f"   {line_id}: {filled:>2}/{capacity:>2} ({utilization:>5.2f}%) {bar}\n"
    
    return result.strip()


def generate_recommendations(changeover_rate, penalties, total_cycles, utilization, overflows):
    """Generate actionable recommendations"""
    recommendations = []
    priority = 1
    
    if changeover_rate > 50:
        recommendations.append(f"   [{priority}] CRITICAL: Implement advanced color batching algorithm to reduce changeovers.")
        priority += 1
    
    if penalties > total_cycles * 0.15:
        recommendations.append(f"   [{priority}] HIGH: Increase O1 buffer capacity or optimize O1 placement logic.")
        priority += 1
    
    if utilization > 80:
        recommendations.append(f"   [{priority}] HIGH: System near capacity. Consider adding additional buffer lines.")
        priority += 1
    elif utilization < 30:
        recommendations.append(f"   [{priority}] MEDIUM: Low utilization. Reduce buffer capacity to optimize space.")
        priority += 1
    
    if overflows > 0:
        recommendations.append(f"   [{priority}] CRITICAL: Buffer overflows detected. Immediate capacity increase required.")
        priority += 1
    
    if not recommendations:
        recommendations.append("   [✓] System operating optimally. Continue monitoring for sustained performance.")
    
    return '\n'.join(recommendations)


def format_recent_activity():
    """Format recent activity log"""
    activities = st.session_state.recent_placements[:20]
    if not activities:
        return "   No activity recorded yet."
    
    result = ""
    for activity in activities:
        cycle = activity['cycle']
        activity_type = activity.get('type', 'Full Cycle')
        result += f"\n   Cycle {cycle} - {activity_type}:\n"
        
        if 'o1' in activity:
            o1 = activity['o1']
            penalty_marker = " ⚠️ PENALTY" if o1.get('penalty') else ""
            result += f"      O1: {o1['color']} → Buffer {o1['buffer']}{penalty_marker}\n"
        
        if 'o2' in activity:
            o2 = activity['o2']
            buffer_display = o2['buffer'] if o2['buffer'] != 'TMP_BUFFER' else 'Temp Buffer (Blocked)'
            result += f"      O2: {o2['color']} → {buffer_display}\n"
        
        if 'o2_temp_processed' in activity:
            tmp = activity['o2_temp_processed']
            result += f"      O2 Temp→Buffer: {tmp['color']} (ID #{tmp['id']}) → {tmp['buffer']}\n"
        
        if 'conveyor' in activity:
            conv = activity['conveyor']
            result += f"      Main Conveyor: {conv['color']} (ID #{conv['id']}) ← from {conv['buffer']}\n"
    
    return result


def format_conveyor_sequence():
    """Format main conveyor sequence"""
    sequence = st.session_state.system.main_conveyor_sequence[-50:]
    if not sequence:
        return "   No vehicles processed yet."
    
    result = ""
    for i, vehicle in enumerate(reversed(sequence), 1):
        result += f"   {len(st.session_state.system.main_conveyor_sequence) - i + 1:>4}. {vehicle['color']:>4} (ID #{vehicle['id']:<4}) from {vehicle['buffer']}\n"
    
    return result.strip()


def generate_pdf_report() -> BytesIO:
    """Generate a comprehensive PDF report"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1f4788'),
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=6,
        spaceBefore=6,
        fontName='Helvetica-Bold'
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 10
    normal_style.leading = 14
    
    # Get system data
    system = st.session_state.system
    current_time = datetime.datetime.now()
    start_time = st.session_state.simulation_start_time
    runtime_delta = current_time - start_time
    
    # Calculate metrics
    total_cycles = st.session_state.cycle
    total_processed = system.total_processed
    changeovers = system.color_changeovers
    penalties = system.penaltyCount
    buffer_overflows = st.session_state.buffer_overflow_count
    
    if total_cycles > 0:
        avg_jobs_per_hour = (total_processed / total_cycles) * 60
    else:
        avg_jobs_per_hour = 0
    
    if total_processed > 0:
        changeover_rate = (changeovers / total_processed) * 100
    else:
        changeover_rate = 0
    
    # Buffer utilization
    buffer_stats = {}
    total_capacity = 0
    total_filled = 0
    
    for line_id, buffer_line in system.buffer_lines.items():
        capacity = buffer_line.capacity
        filled = buffer_line.get_filled_length()
        utilization = (filled / capacity * 100) if capacity > 0 else 0
        buffer_stats[line_id] = {
            'capacity': capacity,
            'filled': filled,
            'utilization': utilization
        }
        total_capacity += capacity
        total_filled += filled
    
    overall_utilization = (total_filled / total_capacity * 100) if total_capacity > 0 else 0
    
    # Color distribution analysis
    color_counts = {}
    for vehicle_data in system.main_conveyor_sequence:
        color = vehicle_data['color']
        color_counts[color] = color_counts.get(color, 0) + 1
    
    # Title Page
    elements.append(Spacer(1, 1*inch))
    elements.append(Paragraph("TATA MOTORS", title_style))
    elements.append(Paragraph("Conveyor System Performance Analysis Report", heading_style))
    elements.append(Spacer(1, 0.5*inch))
    
    # Report metadata
    metadata_data = [
        ['Report Generated:', current_time.strftime('%Y-%m-%d %H:%M:%S')],
        ['Simulation Started:', start_time.strftime('%Y-%m-%d %H:%M:%S')],
        ['Total Runtime:', f"{runtime_delta.total_seconds():.2f} seconds ({runtime_delta.total_seconds()/60:.2f} minutes)"],
        ['Report ID:', f"RPT-{current_time.strftime('%Y%m%d-%H%M%S')}"]
    ]
    
    metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
    metadata_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f0f7')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(metadata_table)
    elements.append(PageBreak())
    
    # Executive Summary
    elements.append(Paragraph("EXECUTIVE SUMMARY", heading_style))
    elements.append(Paragraph("Key Performance Indicators", subheading_style))
    
    kpi_data = [
        ['Metric', 'Value', 'Relevance'],
        ['Total Cycles Run', str(total_cycles), 'Simulation duration'],
        ['Total Vehicles Processed', str(total_processed), 'Throughput measurement'],
        ['Color Changeovers', str(changeovers), 'Inefficiency indicator'],
        ['Buffer Overflows', str(buffer_overflows), 'Bottleneck detection'],
        ['O1 Penalties', str(penalties), 'Improper routing'],
        ['Avg Jobs/Hour (est.)', f"{avg_jobs_per_hour:.2f}", 'Productivity measure'],
        ['Last Processed Color', system.main_conveyor_last_color if system.main_conveyor_last_color else 'N/A', 'Continuity analysis'],
        ['O2 Temp Buffer Queue', str(len(system.o2_temp_buffer)), 'Blocking status']
    ]
    
    kpi_table = Table(kpi_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(kpi_table)
    elements.append(Spacer(1, 0.3*inch))
    
    
    # Detailed Analysis
    elements.append(PageBreak())
    elements.append(Paragraph("DETAILED ANALYSIS", heading_style))
    
    # 1. Throughput Analysis
    elements.append(Paragraph("1. Throughput Analysis", subheading_style))
    throughput_text = f"""
    <b>Total vehicles processed:</b> {total_processed}<br/>
    <b>Total cycles executed:</b> {total_cycles}<br/>
    <b>Processing efficiency:</b> {(total_processed/total_cycles*100) if total_cycles > 0 else 0:.2f}%<br/>
    <b>Estimated production rate:</b> {avg_jobs_per_hour:.2f} vehicles/hour<br/><br/>
    <b>INSIGHT:</b> {'Production rate is optimal.' if avg_jobs_per_hour >= 50 else 'Production rate needs improvement. Consider optimizing buffer allocation.'}
    """
    elements.append(Paragraph(throughput_text, normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # 2. Color Changeover Analysis
    elements.append(Paragraph("2. Color Changeover Analysis", subheading_style))
    changeover_text = f"""
    <b>Total changeovers:</b> {changeovers}<br/>
    <b>Changeover rate:</b> {changeover_rate:.2f}%<br/>
    <b>Average vehicles between changeovers:</b> {(total_processed/changeovers) if changeovers > 0 else total_processed:.2f}<br/><br/>
    <b>INSIGHT:</b> {'Excellent color sequencing - minimal changeovers.' if changeover_rate < 30 else 'High changeover rate detected. Consider improving color batching strategy.' if changeover_rate < 50 else 'Critical: Very high changeover rate. Buffer sequencing algorithm needs optimization.'}
    """
    elements.append(Paragraph(changeover_text, normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # 3. Buffer Utilization
    elements.append(Paragraph("3. Buffer Utilization Analysis", subheading_style))
    buffer_text = f"<b>Overall System Utilization:</b> {overall_utilization:.2f}%<br/><br/>"
    elements.append(Paragraph(buffer_text, normal_style))
    
    # Buffer utilization table
    buffer_util_data = [['Buffer ID', 'Filled/Capacity', 'Utilization %']]
    for line_id in sorted(buffer_stats.keys()):
        stats = buffer_stats[line_id]
        buffer_util_data.append([
            line_id,
            f"{stats['filled']}/{stats['capacity']}",
            f"{stats['utilization']:.1f}%"
        ])
    
    buffer_table = Table(buffer_util_data, colWidths=[1.5*inch, 2*inch, 2*inch])
    buffer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    
    elements.append(buffer_table)
    elements.append(Spacer(1, 0.15*inch))
    
    buffer_insight = f"<b>INSIGHT:</b> {'Balanced buffer utilization across the system.' if 30 <= overall_utilization <= 70 else 'Warning: Buffer utilization is suboptimal. Review allocation strategy.' if overall_utilization < 30 else 'Critical: Buffers near capacity. Risk of bottlenecks.'}"
    elements.append(Paragraph(buffer_insight, normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # 4. O1 Penalty Analysis
    elements.append(Paragraph("4. O1 Penalty Analysis", subheading_style))
    penalty_rate = (penalties/total_cycles*100) if total_cycles > 0 else 0
    penalty_text = f"""
    <b>Total O1 penalties:</b> {penalties}<br/>
    <b>Penalty rate:</b> {penalty_rate:.2f}%<br/>
    <b>O1 vehicles routed to O2 buffers:</b> {penalties}<br/><br/>
    <b>INSIGHT:</b> {'No routing issues detected.' if penalties == 0 else 'Minor routing inefficiency detected.' if penalties < total_cycles * 0.1 else 'Significant routing issues. O1 buffers frequently full, causing O2 buffer usage.'}
    """
    elements.append(Paragraph(penalty_text, normal_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # 5. Blocking Analysis
    elements.append(Paragraph("5. Blocking & Overflow Analysis", subheading_style))
    blocking_text = f"""
    <b>Buffer overflows detected:</b> {buffer_overflows}<br/>
    <b>O2 temporary buffer queue:</b> {len(system.o2_temp_buffer)} vehicles waiting<br/>
    <b>O2 blocked status:</b> {'ACTIVE' if system.o2Stopped else 'NORMAL'}<br/><br/>
    <b>INSIGHT:</b> {'No blocking issues. System operating smoothly.' if buffer_overflows == 0 and len(system.o2_temp_buffer) == 0 else 'System experiencing blocking. Consider increasing buffer capacity or optimizing placement logic.'}
    """
    elements.append(Paragraph(blocking_text, normal_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Recent Activity
    elements.append(PageBreak())
    elements.append(Paragraph("RECENT ACTIVITY LOG (Last 15 Cycles)", heading_style))
    
    activities = st.session_state.recent_placements[:15]
    if activities:
        for activity in activities:
            cycle = activity['cycle']
            activity_type = activity.get('type', 'Full Cycle')
            activity_text = f"<b>Cycle {cycle} - {activity_type}:</b><br/>"
            
            if 'o1' in activity:
                o1 = activity['o1']
                penalty_marker = " ⚠️ PENALTY" if o1.get('penalty') else " ✅"
                activity_text += f"&nbsp;&nbsp;&nbsp;&nbsp;O1: {o1['color']} → Buffer {o1['buffer']}{penalty_marker}<br/>"
            
            if 'o2' in activity:
                o2 = activity['o2']
                buffer_display = o2['buffer'] if o2['buffer'] != 'TMP_BUFFER' else 'Temp Buffer (Blocked)'
                activity_text += f"&nbsp;&nbsp;&nbsp;&nbsp;O2: {o2['color']} → {buffer_display}<br/>"
            
            if 'conveyor' in activity:
                conv = activity['conveyor']
                activity_text += f"&nbsp;&nbsp;&nbsp;&nbsp;Main Conveyor: {conv['color']} (ID #{conv['id']}) ← from {conv['buffer']}<br/>"
            
            elements.append(Paragraph(activity_text, normal_style))
            elements.append(Spacer(1, 0.1*inch))
    else:
        elements.append(Paragraph("No activity recorded yet.", normal_style))
    
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


# ------------------------------
# STREAMLIT UI
# ------------------------------

def render_color_box(color: str, size: int = 20):
    """Render a colored box with HTML"""
    hex_color = COLOR_MAP.get(color, "#888888")
    return f'<div style="display:inline-block; width:{size}px; height:{size}px; background-color:{hex_color}; border:1px solid #333; border-radius:3px; margin:2px;" title="{color}"></div>'


def main():
    st.set_page_config(page_title="Conveyor Sequencing Simulator", layout="wide", initial_sidebar_state="expanded")
    
    # Custom CSS
    st.markdown("""
        <style>
        .main {background-color: #0e1117;}
        .stButton>button {width: 100%;}
        .buffer-row {padding: 10px; border-radius: 5px; margin: 5px 0; background-color: #1e1e1e;}
        .jph-display {background-color: #2e7d32; padding: 10px; border-radius: 5px; color: white; font-weight: bold; text-align: center;}
        .time-breakdown {background-color: #1e3a5f; padding: 10px; border-radius: 5px; color: white;}
        .comparison-card {background-color: #1e1e1e; padding: 15px; border-radius: 10px; margin: 10px 0; border: 2px solid #333;}
        .algorithm-badge {padding: 5px 10px; border-radius: 15px; color: white; font-size: 12px; font-weight: bold; display: inline-block;}
        .graph-container {background-color: #1e1e1e; padding: 20px; border-radius: 10px; margin: 10px 0;}
        .temp-buffer-box {
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            border: 3px solid #ff8c42;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            box-shadow: 0 4px 6px rgba(255, 107, 53, 0.3);
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("Smart Conveyor Sequencing Simulator")
    st.markdown("**1s per vehicle + 1s penalties for inefficiencies**")
    
    # Initialize session state
    if 'system' not in st.session_state:
        st.session_state.system = ConveyorSystem()
        st.session_state.round_robin_system = SimpleRoundRobinConveyorSystem()
        st.session_state.cycle = 0
        st.session_state.running = False
        st.session_state.recent_placements = []
        st.session_state.current_o1 = None
        st.session_state.current_o2 = None
        st.session_state.pending_o1_body = None
        st.session_state.pending_o2_body = None
        st.session_state.o2_temp_processed = []
        st.session_state.penalty_log = []
        st.session_state.jph_history = []
        st.session_state.penalty_history = []
        st.session_state.color_change_history = []
        st.session_state.simulation_start_time = datetime.datetime.now()
        st.session_state.buffer_overflow_count = 0
        st.session_state.total_runtime_seconds = 0
    
    # Update JPH for both systems
    st.session_state.system.update_jph()
    st.session_state.round_robin_system.update_jph()
    
    # Update history for graphs
    if st.session_state.cycle > 0:
        st.session_state.jph_history.append({
            'cycle': st.session_state.cycle,
            'optimized_jph': st.session_state.system.jph,
            'round_robin_jph': st.session_state.round_robin_system.jph
        })
        
        st.session_state.penalty_history.append({
            'cycle': st.session_state.cycle,
            'optimized_penalties': st.session_state.system.penaltyCount,
            'round_robin_penalties': st.session_state.round_robin_system.penaltyCount
        })
        
        st.session_state.color_change_history.append({
            'cycle': st.session_state.cycle,
            'optimized_changes': st.session_state.system.color_changeovers,
            'round_robin_changes': st.session_state.round_robin_system.color_changeovers
        })
    
    # Sidebar controls
    with st.sidebar:
        st.header("Control Panel")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Start" if not st.session_state.running else "Pause"):
                st.session_state.running = not st.session_state.running
        
        with col2:
            if st.button("Reset"):
                st.session_state.system = ConveyorSystem()
                st.session_state.round_robin_system = SimpleRoundRobinConveyorSystem()
                st.session_state.cycle = 0
                st.session_state.running = False
                st.session_state.recent_placements = []
                st.session_state.current_o1 = None
                st.session_state.current_o2 = None
                st.session_state.pending_o1_body = None
                st.session_state.pending_o2_body = None
                st.session_state.o2_temp_processed = []
                st.session_state.penalty_log = []
                st.session_state.jph_history = []
                st.session_state.penalty_history = []
                st.session_state.color_change_history = []
                st.session_state.simulation_start_time = datetime.datetime.now()
                st.session_state.buffer_overflow_count = 0
                st.rerun()
        
        speed = st.select_slider("Simulation Speed", options=[0.5, 1, 2, 3], value=1, format_func=lambda x: f"{x}x")
        
        st.divider()
        st.markdown("**Manual Step-by-Step Controls:**")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Generate Colors", use_container_width=True):
                generate_oven_colors_only()
                st.rerun()
        
        with col_btn2:
            if st.button("Place in Buffers", use_container_width=True):
                place_oven_vehicles_in_buffers()
                st.rerun()
        
        col_btn3, col_btn4 = st.columns(2)
        with col_btn3:
            if st.button("Conveyor Extract", use_container_width=True):
                run_conveyor_cycle_only()
                st.rerun()
        
        with col_btn4:
            if st.button("Full Cycle", use_container_width=True):
                run_single_cycle()
                st.rerun()

        # Download Report Button - MOVED HERE
        st.divider()
        st.subheader("Generate Report")
        if st.button("Generate PDF Report", use_container_width=True):
            try:
                pdf_buffer = generate_pdf_report()
                st.download_button(
                    label="Download PDF Report",
                    data=pdf_buffer,
                    file_name=f"conveyor_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
                st.success("Report generated successfully!")
            except Exception as e:
                st.error(f"Error generating report: {str(e)}")
                st.info("Make sure reportlab is installed: pip install reportlab")
        
        st.divider()
        
        st.subheader("Performance Comparison")
        
        # JPH Comparison
        optimized_jph = st.session_state.system.jph
        round_robin_jph = st.session_state.round_robin_system.jph
        
        col_jph1, col_jph2 = st.columns(2)
        with col_jph1:
            st.metric("Optimized JPH", f"{optimized_jph:.1f}")
        with col_jph2:
            st.metric("Round Robin JPH", f"{round_robin_jph:.1f}")
        
        # Performance difference
        if optimized_jph > 0 and round_robin_jph > 0:
            improvement = ((optimized_jph - round_robin_jph) / round_robin_jph) * 100
            st.metric("Performance Improvement", f"{improvement:.1f}%", 
                     delta=f"{optimized_jph - round_robin_jph:.1f} JPH")
        
        st.divider()
        
        st.subheader("Optimized Algorithm Details")
        
        st.metric("Cycle", st.session_state.cycle)
        st.metric("Total Processed", st.session_state.system.total_processed)
        st.metric("Color Changeovers", st.session_state.system.color_changeovers)
        st.metric("O1 Violations", st.session_state.system.penaltyCount)
        st.metric("O2 Temp Buffer", len(st.session_state.system.o2_temp_buffer))
        
        # Time breakdown
        time_breakdown = st.session_state.system.get_time_breakdown()
        
        st.markdown('<div class="time-breakdown">', unsafe_allow_html=True)
        st.metric("Base Processing Time", f"{time_breakdown['base_processing_time']:.1f}s")
        st.metric("Penalty Time", f"{time_breakdown['penalty_time']:.1f}s")
        st.metric("Total Effective Time", f"{time_breakdown['total_effective_time']:.1f}s")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Buffer Line Controls
        st.divider()
        st.subheader("Buffer Line Controls")

        for line_id in sorted(st.session_state.system.buffer_lines.keys()):
            buffer_line = st.session_state.system.buffer_lines[line_id]
            
            col1, col2 = st.columns([1, 1])
            with col1:
                toggle_input = st.checkbox(f"{line_id} Input", value=buffer_line.is_available_input, key=f"{line_id}_input")
            with col2:
                toggle_output = st.checkbox(f"{line_id} Output", value=buffer_line.is_available_output, key=f"{line_id}_output")
            
            buffer_line.is_available_input = toggle_input
            buffer_line.is_available_output = toggle_output
        
        if st.session_state.system.main_conveyor_last_color:
            st.markdown("**Last Color:**")
            st.markdown(render_color_box(st.session_state.system.main_conveyor_last_color, 30) + 
                       f" {st.session_state.system.main_conveyor_last_color}", unsafe_allow_html=True)
        
        st.divider()
        st.subheader("Color Legend")
        for color in ALL_COLORS:
            st.markdown(render_color_box(color, 20) + f" **{color}** ({COLOR_DISTRIBUTION[color]*100:.0f}%)", 
                       unsafe_allow_html=True)
        
        # Penalty log
        if st.session_state.penalty_log:
            st.divider()
            st.subheader("Penalty Log (1s each)")
            for log in reversed(st.session_state.penalty_log[-5:]):
                st.error(f"{log['time']} - {log['reason']}")
    
    # Main content - SIMULATION FIRST
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        # Ovens section
        st.subheader("Ovens Output")
        oven_col1, oven_col2 = st.columns(2)
        
        with oven_col1:
            st.markdown("**Oven 1 (O1)**")
            if st.session_state.pending_o1_body:
                st.markdown("**Ready to place:**")
                st.markdown(render_color_box(st.session_state.current_o1, 40) + 
                           f" **{st.session_state.current_o1}**", unsafe_allow_html=True)
            elif st.session_state.current_o1:
                st.markdown("**Placed:**")
                st.markdown(render_color_box(st.session_state.current_o1, 40) + 
                           f" **{st.session_state.current_o1}**", unsafe_allow_html=True)
            else:
                st.info("Waiting...")
        
        with oven_col2:
            st.markdown("**Oven 2 (O2)**")
            
            # Show O2 blocked status
            if st.session_state.system.o2Stopped:
                st.error("O2 BLOCKED!")
            
            if st.session_state.pending_o2_body:
                st.markdown("**Ready to place:**")
                st.markdown(render_color_box(st.session_state.current_o2, 40) + 
                           f" **{st.session_state.current_o2}**", unsafe_allow_html=True)
            elif st.session_state.current_o2:
                st.markdown("**Placed:**")
                st.markdown(render_color_box(st.session_state.current_o2, 40) + 
                           f" **{st.session_state.current_o2}**", unsafe_allow_html=True)
            else:
                st.info("Waiting...")
        
        st.divider()
        
        # O2 Temporary Buffer Display
        if st.session_state.system.o2_temp_buffer or st.session_state.system.o2Stopped:
            st.subheader("O2 Temporary Buffer")
            
            if st.session_state.system.o2Stopped:
                st.error("O2 is currently BLOCKED")
            
            temp_buffer_size = len(st.session_state.system.o2_temp_buffer)
            
            # Buffer header
            col1, col2 = st.columns([1, 6])
            with col1:
                st.markdown(f"**TMP**")
            with col2:
                # Create visual boxes for temp buffer
                boxes_html = '<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">'
                
                # Filled boxes (with colors) - showing vehicles in temp buffer
                for body in st.session_state.system.o2_temp_buffer:
                    hex_color = COLOR_MAP.get(body.color, "#888888")
                    boxes_html += f'<div style="width:25px; height:25px; background-color:{hex_color}; border:1px solid #ff8c42; border-radius:3px; display:inline-flex; align-items:center; justify-content:center; font-size:8px; color:#fff; font-weight:bold;" title="{body.color} (ID: {body.body_id})"></div>'
                
                # Add count indicator
                boxes_html += f'<div style="margin-left: 10px; font-size: 12px; color: #ff8c42; font-weight: bold;">({temp_buffer_size} waiting)</div>'
                boxes_html += '</div>'
                
                st.markdown(boxes_html, unsafe_allow_html=True)
            
            st.markdown("---")
        
        st.divider()
        
        # Buffer lines
        st.subheader("Buffer Lines (Optimized Algorithm)")
        
        for line_id in sorted(st.session_state.system.buffer_lines.keys()):
            buffer = st.session_state.system.buffer_lines[line_id]
            is_o1 = line_id in O1_BUFFERS
            
            capacity = buffer.capacity
            filled = buffer.get_filled_length()
            
            # Buffer header
            col1, col2 = st.columns([1, 6])
            with col1:
                badge = "O1" if is_o1 else "O2"
                st.markdown(f"**{line_id}** {badge}")
            with col2:
                # Create visual boxes for buffer capacity
                boxes_html = '<div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">'
                
                # Filled boxes (with colors)
                for body in buffer.queue:
                    hex_color = COLOR_MAP.get(body.color, "#888888")
                    boxes_html += f'<div style="width:25px; height:25px; background-color:{hex_color}; border:1px solid #333; border-radius:3px; display:inline-flex; align-items:center; justify-content:center; font-size:8px; color:#fff; font-weight:bold;" title="{body.color}"></div>'
                
                # Empty boxes
                for _ in range(capacity - filled):
                    boxes_html += f'<div style="width:25px; height:25px; background-color:#2a2a2a; border:1px dashed #555; border-radius:3px; display:inline-flex;" title="Empty"></div>'
                
                # Add capacity indicator
                boxes_html += f'<div style="margin-left: 10px; font-size: 12px; color: #aaa;">({filled}/{capacity})</div>'
                boxes_html += '</div>'
                
                st.markdown(boxes_html, unsafe_allow_html=True)
            
            st.markdown("---")
    
    with col_right:
        # Main conveyor
        st.subheader("Main Conveyor")
        st.markdown("**Recent 10 vehicles:**")
        
        if st.session_state.system.main_conveyor_sequence:
            recent_10 = st.session_state.system.main_conveyor_sequence[-10:]
            for i, vehicle_data in enumerate(reversed(recent_10)):
                vehicle_num = len(st.session_state.system.main_conveyor_sequence) - i
                color = vehicle_data['color']
                buffer = vehicle_data['buffer']
                vehicle_id = vehicle_data['id']
                color_change = vehicle_data.get('color_change', False)
                
                penalty_indicator = " +1s" if color_change else ""
                st.markdown(
                    f"{render_color_box(color, 25)} **{color}** | #{vehicle_id} | from **{buffer}**{penalty_indicator}",
                    unsafe_allow_html=True
                )
        else:
            st.info("No vehicles processed yet")
        
        st.divider()
        
        # Recent activity
        st.subheader("Recent Activity")
        for placement in st.session_state.recent_placements[:5]:
            cycle_type = placement.get('type', 'Full Cycle')
            with st.expander(f"Cycle {placement['cycle']} - {cycle_type}", expanded=False):
                if 'o1' in placement:
                    penalty_text = " +1s (O1 used L5-L9)" if placement['o1'].get('penalty_applied', False) else ""
                    st.markdown(f"**O1:** {render_color_box(placement['o1']['color'], 20)} {placement['o1']['color']} → {placement['o1']['buffer']}{penalty_text}", 
                               unsafe_allow_html=True)
                if 'o2' in placement:
                    buffer_display = placement['o2']['buffer'] if placement['o2']['buffer'] != 'TMP_BUFFER' else 'Temp Buffer'
                    st.markdown(f"**O2:** {render_color_box(placement['o2']['color'], 20)} {placement['o2']['color']} → {buffer_display}", 
                               unsafe_allow_html=True)
                if 'o2_temp_processed' in placement:
                    tmp = placement['o2_temp_processed']
                    st.markdown(f"**O2 Temp→Buffer:** {render_color_box(tmp['color'], 20)} {tmp['color']} (ID: #{tmp['id']}) → {tmp['buffer']}", 
                               unsafe_allow_html=True)
                if 'conveyor' in placement:
                    conv = placement['conveyor']
                    color_change_text = " +1s (Color Change)" if conv.get('color_change', False) else ""
                    st.markdown(f"**Main Conveyor:** {render_color_box(conv['color'], 20)} {conv['color']} (ID: #{conv['id']}) ← from **{conv['buffer']}**{color_change_text}", 
                               unsafe_allow_html=True)

    # ALGORITHM COMPARISON SECTION - MOVED BELOW SIMULATION
    st.markdown("---")
    st.subheader("Algorithm Comparison")
    
    col_comp1, col_comp2 = st.columns(2)
    
    with col_comp1:
        st.markdown('<div class="comparison-card">', unsafe_allow_html=True)
        st.markdown('<div class="algorithm-badge" style="background-color: #2e7d32;">Optimized Algorithm</div>', unsafe_allow_html=True)
        st.metric("Current JPH", f"{st.session_state.system.jph:.1f}")
        st.metric("Color Changeovers", st.session_state.system.color_changeovers)
        st.metric("O1 Violations", st.session_state.system.penaltyCount)
        st.metric("O2 Temp Buffer", len(st.session_state.system.o2_temp_buffer))
        st.markdown("""
        **Strategy:**
        - Color grouping optimization
        - Minimize color changes
        - Smart buffer selection
        - Priority-based placement
        - Temporary buffer for O2 blocking
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_comp2:
        st.markdown('<div class="comparison-card">', unsafe_allow_html=True)
        st.markdown('<div class="algorithm-badge" style="background-color: #7e57c2;">Round Robin</div>', unsafe_allow_html=True)
        st.metric("Current JPH", f"{st.session_state.round_robin_system.jph:.1f}")
        st.metric("Color Changeovers", st.session_state.round_robin_system.color_changeovers)
        st.metric("O1 Violations", st.session_state.round_robin_system.penaltyCount)
        st.markdown("""
        **Strategy:**
        - Simple round-robin
        - No color consideration
        - Sequential buffer usage
        - Basic fairness
        """)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # SIMPLIFIED GRAPHS SECTION - Only keeping JPH and Penalty Analysis line graphs
    if st.session_state.cycle > 0:
        st.markdown("---")
        st.subheader("Performance Analysis")
        
        # Convert history to DataFrames
        if st.session_state.jph_history:
            jph_df = pd.DataFrame(st.session_state.jph_history)
            penalty_df = pd.DataFrame(st.session_state.penalty_history)
            
            # 1. JPH Comparison Over Time
            st.markdown('<div class="graph-container">', unsafe_allow_html=True)
            st.subheader("JPH Performance Over Time")
            
            # Line chart for JPH over time
            chart_data = pd.DataFrame({
                'Cycle': jph_df['cycle'],
                'Optimized Algorithm': jph_df['optimized_jph'],
                'Round Robin': jph_df['round_robin_jph']
            })
            st.line_chart(chart_data.set_index('Cycle'), use_container_width=True)
            
            # Current JPH comparison
            col_jph1, col_jph2, col_jph3 = st.columns(3)
            with col_jph1:
                st.metric("Optimized JPH", f"{st.session_state.system.jph:.1f}")
            with col_jph2:
                st.metric("Round Robin JPH", f"{st.session_state.round_robin_system.jph:.1f}")
            with col_jph3:
                improvement = ((st.session_state.system.jph - st.session_state.round_robin_system.jph) / st.session_state.round_robin_system.jph * 100) if st.session_state.round_robin_system.jph > 0 else 0
                st.metric("Improvement", f"{improvement:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # 2. Penalty Analysis - Line Graph Only
            st.markdown('<div class="graph-container">', unsafe_allow_html=True)
            st.subheader("Penalty Analysis")
            
            # Line chart for cumulative penalties over time
            penalty_chart_data = pd.DataFrame({
                'Cycle': penalty_df['cycle'],
                'Optimized Penalties': penalty_df['optimized_penalties'],
                'Round Robin Penalties': penalty_df['round_robin_penalties']
            })
            st.line_chart(penalty_chart_data.set_index('Cycle'), use_container_width=True)
            
            # Current penalty comparison
            col_pen1, col_pen2, col_pen3 = st.columns(3)
            with col_pen1:
                st.metric("Optimized Penalties", st.session_state.system.penaltyCount)
            with col_pen2:
                st.metric("Round Robin Penalties", st.session_state.round_robin_system.penaltyCount)
            with col_pen3:
                penalty_reduction = ((st.session_state.round_robin_system.penaltyCount - st.session_state.system.penaltyCount) / st.session_state.round_robin_system.penaltyCount * 100) if st.session_state.round_robin_system.penaltyCount > 0 else 100
                st.metric("Penalty Reduction", f"{penalty_reduction:.1f}%")
            st.markdown('</div>', unsafe_allow_html=True)
    
    # Auto-run simulation
    if st.session_state.running:
        time.sleep(1 / speed)
        run_single_cycle()
        st.rerun()


def generate_oven_colors_only():
    """Only generate colors for both ovens - don't place them yet"""
    system = st.session_state.system
    round_robin_system = st.session_state.round_robin_system
    
    # Generate colors (same for both systems for fair comparison)
    o1_color = generate_vehicle_color()
    o2_color = generate_vehicle_color()
    
    st.session_state.current_o1 = o1_color
    st.session_state.current_o2 = o2_color
    
    # Create bodies but keep them pending
    o1_body = VehicleBody(system.body_counter + 1, o1_color, OvenType.O1)
    system.body_counter += 1
    o2_body = VehicleBody(system.body_counter + 1, o2_color, OvenType.O2)
    system.body_counter += 1
    
    # Also create bodies for round-robin system
    rr_o1_body = VehicleBody(round_robin_system.body_counter + 1, o1_color, OvenType.O1)
    round_robin_system.body_counter += 1
    rr_o2_body = VehicleBody(round_robin_system.body_counter + 1, o2_color, OvenType.O2)
    round_robin_system.body_counter += 1
    
    st.session_state.pending_o1_body = o1_body
    st.session_state.pending_o2_body = o2_body


def place_oven_vehicles_in_buffers():
    """Place pending vehicles from ovens into buffers for both systems"""
    system = st.session_state.system
    round_robin_system = st.session_state.round_robin_system
    
    if not st.session_state.pending_o1_body and not st.session_state.pending_o2_body:
        return  # Nothing to place
    
    # Place in optimized system
    o1_buffer = None
    o2_buffer = None
    penalty_o1 = False
    penalty_applied_o1 = False
    
    # Place O1 vehicle in optimized system
    if st.session_state.pending_o1_body:
        o1_body = st.session_state.pending_o1_body
        o1_buffer, penalty_o1, penalty_applied_o1 = system.place_for_o1(o1_body)
        
        # Also place in round-robin system
        rr_o1_body = VehicleBody(round_robin_system.body_counter, o1_body.color, OvenType.O1)
        round_robin_system.place_for_o1(rr_o1_body)
        
        st.session_state.pending_o1_body = None
        
        # Log penalty if applied
        if penalty_applied_o1:
            if 'penalty_log' not in st.session_state:
                st.session_state.penalty_log = []
            st.session_state.penalty_log.append({
                'time': datetime.datetime.now().strftime("%H:%M:%S"),
                'reason': "O1 used L5-L9 buffer"
            })
    
    # Handle O2: If temp buffer has vehicles AND O2 is unblocked, process from temp buffer
    temp_processed = None
    if st.session_state.pending_o2_body:
        o2_body = st.session_state.pending_o2_body
        
        # Check if we should process from temp buffer (optimized system only)
        if not system.o2Stopped and system.o2_temp_buffer:
            # Process ONE vehicle from temp buffer
            temp_processed = system.process_o2_temp_buffer()
            if temp_processed:
                st.session_state.o2_temp_processed.insert(0, {
                    'cycle': st.session_state.cycle + 1,
                    'body': temp_processed[0],
                    'buffer': temp_processed[1]
                })
        
        # Now handle the new O2 vehicle (will go to temp buffer if temp buffer has items or O2 is blocked)
        o2_buffer = system.place_for_o2(o2_body)
        
        # Also place in round-robin system
        if not round_robin_system.o2Stopped:
            rr_o2_body = VehicleBody(round_robin_system.body_counter, o2_body.color, OvenType.O2)
            round_robin_system.place_for_o2(rr_o2_body)
        
        st.session_state.pending_o2_body = None
    
    # Record placement
    placement_record = {
        'cycle': st.session_state.cycle + 1,
        'o1': {'color': st.session_state.current_o1, 'buffer': o1_buffer, 'penalty': penalty_o1, 'penalty_applied': penalty_applied_o1},
        'o2': {'color': st.session_state.current_o2, 'buffer': o2_buffer},
        'type': 'Placement Only'
    }
    
    if temp_processed:
        placement_record['o2_temp_processed'] = {
            'color': temp_processed[0].color,
            'buffer': temp_processed[1],
            'id': temp_processed[0].body_id
        }
    
    st.session_state.recent_placements.insert(0, placement_record)
    st.session_state.cycle += 1


def run_single_cycle():
    """Execute one simulation cycle for both systems"""
    system = st.session_state.system
    round_robin_system = st.session_state.round_robin_system
    
    # Generate colors (same for both systems for fair comparison)
    o1_color = generate_vehicle_color()
    o2_color = generate_vehicle_color()
    
    st.session_state.current_o1 = o1_color
    st.session_state.current_o2 = o2_color
    
    # Create bodies for optimized system
    o1_body = VehicleBody(system.body_counter + 1, o1_color, OvenType.O1)
    system.body_counter += 1
    o2_body = VehicleBody(system.body_counter + 1, o2_color, OvenType.O2)
    system.body_counter += 1
    
    # Create bodies for round-robin system
    rr_o1_body = VehicleBody(round_robin_system.body_counter + 1, o1_color, OvenType.O1)
    round_robin_system.body_counter += 1
    rr_o2_body = VehicleBody(round_robin_system.body_counter + 1, o2_color, OvenType.O2)
    round_robin_system.body_counter += 1
    
    # Place vehicles in optimized system
    o1_buffer, penalty_o1, penalty_applied_o1 = system.place_for_o1(o1_body)
    
    # Handle O2: If temp buffer has vehicles AND O2 is unblocked, process from temp buffer
    temp_processed = None
    
    # Check if we should process from temp buffer (optimized system only)
    if not system.o2Stopped and system.o2_temp_buffer:
        # Process ONE vehicle from temp buffer
        temp_processed = system.process_o2_temp_buffer()
        if temp_processed:
            st.session_state.o2_temp_processed.insert(0, {
                'cycle': st.session_state.cycle + 1,
                'body': temp_processed[0],
                'buffer': temp_processed[1]
            })
    
    # Now handle the new O2 vehicle (will go to temp buffer if temp buffer has items or O2 is blocked)
    o2_buffer = system.place_for_o2(o2_body)
    
    # Place vehicles in round-robin system
    round_robin_system.place_for_o1(rr_o1_body)
    if not round_robin_system.o2Stopped:
        round_robin_system.place_for_o2(rr_o2_body)
    
    # Log O1 penalty if applied
    if penalty_applied_o1:
        if 'penalty_log' not in st.session_state:
            st.session_state.penalty_log = []
        st.session_state.penalty_log.append({
            'time': datetime.datetime.now().strftime("%H:%M:%S"),
            'reason': "O1 used L5-L9 buffer"
        })
    
    # Record placement
    placement_record = {
        'cycle': st.session_state.cycle + 1,
        'o1': {'color': o1_color, 'buffer': o1_buffer, 'penalty': penalty_o1, 'penalty_applied': penalty_applied_o1},
        'o2': {'color': o2_color, 'buffer': o2_buffer}
    }
    
    if temp_processed:
        placement_record['o2_temp_processed'] = {
            'color': temp_processed[0].color,
            'buffer': temp_processed[1],
            'id': temp_processed[0].body_id
        }
    
    # Main conveyor extraction for both systems
    selected_buffer_id = system.select_buffer_for_main_conveyor()
    color_change = False
    if selected_buffer_id:
        body = system.buffer_lines[selected_buffer_id].remove_body()
        if body:
            # Check for color change penalty
            if system.main_conveyor_last_color and system.main_conveyor_last_color != body.color:
                system.color_changeovers += 1
                color_change = True
                # Apply color change penalty
                system.total_penalty_time += PENALTY_TIME_COLOR_CHANGE
                
                # Log penalty
                if 'penalty_log' not in st.session_state:
                    st.session_state.penalty_log = []
                st.session_state.penalty_log.append({
                    'time': datetime.datetime.now().strftime("%H:%M:%S"),
                    'reason': "Color change on conveyor"
                })
            
            system.main_conveyor_last_color = body.color
            system.total_processed += 1
            system.main_conveyor_sequence.append({
                'color': body.color, 
                'buffer': selected_buffer_id, 
                'id': body.body_id,
                'color_change': color_change
            })
            
            # Add conveyor info to placement record
            placement_record['conveyor'] = {
                'color': body.color, 
                'buffer': selected_buffer_id, 
                'id': body.body_id,
                'color_change': color_change
            }
    
    # Also extract from round-robin system
    rr_selected_buffer_id = round_robin_system.select_buffer_for_main_conveyor()
    if rr_selected_buffer_id:
        rr_body = round_robin_system.buffer_lines[rr_selected_buffer_id].remove_body()
        if rr_body:
            # Check for color change penalty
            if round_robin_system.main_conveyor_last_color and round_robin_system.main_conveyor_last_color != rr_body.color:
                round_robin_system.color_changeovers += 1
                # Apply color change penalty
                round_robin_system.total_penalty_time += PENALTY_TIME_COLOR_CHANGE
            
            round_robin_system.main_conveyor_last_color = rr_body.color
            round_robin_system.total_processed += 1
    
    st.session_state.recent_placements.insert(0, placement_record)
    st.session_state.cycle += 1


def run_conveyor_cycle_only():
    """Execute only the main conveyor extraction cycle for both systems"""
    system = st.session_state.system
    round_robin_system = st.session_state.round_robin_system
    
    # Main conveyor extraction only for optimized system
    selected_buffer_id = system.select_buffer_for_main_conveyor()
    color_change = False
    if selected_buffer_id:
        body = system.buffer_lines[selected_buffer_id].remove_body()
        if body:
            # Check for color change penalty
            if system.main_conveyor_last_color and system.main_conveyor_last_color != body.color:
                system.color_changeovers += 1
                color_change = True
                # Apply color change penalty
                system.total_penalty_time += PENALTY_TIME_COLOR_CHANGE
                
                # Log penalty
                if 'penalty_log' not in st.session_state:
                    st.session_state.penalty_log = []
                st.session_state.penalty_log.append({
                    'time': datetime.datetime.now().strftime("%H:%M:%S"),
                    'reason': "Color change on conveyor"
                })
            
            system.main_conveyor_last_color = body.color
            system.total_processed += 1
            system.main_conveyor_sequence.append({
                'color': body.color, 
                'buffer': selected_buffer_id, 
                'id': body.body_id,
                'color_change': color_change
            })
            
            # Record conveyor extraction
            st.session_state.recent_placements.insert(0, {
                'cycle': st.session_state.cycle + 1,
                'conveyor': {
                    'color': body.color, 
                    'buffer': selected_buffer_id, 
                    'id': body.body_id,
                    'color_change': color_change
                },
                'type': 'Conveyor Only'
            })
    
    # Also extract from round-robin system
    rr_selected_buffer_id = round_robin_system.select_buffer_for_main_conveyor()
    if rr_selected_buffer_id:
        rr_body = round_robin_system.buffer_lines[rr_selected_buffer_id].remove_body()
        if rr_body:
            # Check for color change penalty
            if round_robin_system.main_conveyor_last_color and round_robin_system.main_conveyor_last_color != rr_body.color:
                round_robin_system.color_changeovers += 1
                # Apply color change penalty
                round_robin_system.total_penalty_time += PENALTY_TIME_COLOR_CHANGE
            
            round_robin_system.main_conveyor_last_color = rr_body.color
            round_robin_system.total_processed += 1
    
    st.session_state.cycle += 1


if __name__ == "__main__":
    main()