#!/usr/bin/env python3
"""
Minimal Pygame UI renderer for Total Annihilation .GUI files (MVP)

- Parses the TDF/INI-style GUI definitions (e.g., extracted_by_go/guis/MAINMENU.GUI)
- Creates a window using the root gadget size
- Renders basic controls (buttons, labels) with hover and click handling
- Supports quickkey activation (ASCII codes in 'quickkey=')

Usage:
  python3 pygame_gui_mvp.py extracted_by_go/guis/MAINMENU.GUI

Notes:
- This is an MVP focused on layout and interaction per docs/UI_PIPELINE.md.
- It does not yet load GAF/PCX art or palettes; controls are drawn with simple shapes.
- Parsing is tailored to common TDF patterns in the extracted GUI files.
"""

import sys
import pygame
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import re

# ----------------------------
# TDF-like parser for .GUI
# ----------------------------

def parse_tdf_gui(path: Path) -> Dict[str, Any]:
    """Parse a TA .GUI (TDF-like) into a nested dict.

    Supports nested sections like:
      [GADGET1]
      {
        [COMMON] { key=value; }
        key=value;
      }

    Parsing semantics enhanced per docs/UI_PIPELINE.md:
      - Preserve duplicate 'text=' lines as multi-line content
      - Keep last value for other duplicate keys (matches common INI semantics)
      - Convert numeric strings (including negatives) to ints
    """
    text = path.read_text(encoding="latin-1")

    def set_in_tree(root: Dict[str, Any], path_list: List[str], key: str, value: Any):
        node = root
        for p in path_list:
            node = node.setdefault(p, {})
        # Preserve multiple text entries; last-wins for others
        if key.lower() == 'text':
            existing = node.get(key)
            if existing is None:
                node[key] = [value]
            elif isinstance(existing, list):
                node[key].append(value)
            else:
                node[key] = [existing, value]
        else:
            node[key] = value

    root: Dict[str, Any] = {}
    section_stack: List[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Skip `//` comments
        if line.startswith('//'):
            continue

        # Section header
        if line.startswith('[') and line.endswith(']'):
            name = line[1:-1].strip()
            section_stack.append(name)
            continue

        # Braces manage nesting depth
        if line.startswith('{'):
            continue
        if line.startswith('}'):
            if section_stack:
                section_stack.pop()
            continue

        # Key-value "key=value;"
        if '=' in line:
            # Remove trailing ';' if present
            if line.endswith(';'):
                line = line[:-1]
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            # Convert to int if possible (incl. negatives)
            if value == "":
                parsed: Any = ""
            else:
                try:
                    parsed = int(value, 10)
                except ValueError:
                    parsed = value
            set_in_tree(root, section_stack, key, parsed)

    return root


# ----------------------------
# Control model
# ----------------------------

class Control:
    def __init__(self, ctype: int, name: str, rect: pygame.Rect, props: Dict[str, Any]):
        self.ctype = ctype
        self.name = name
        self.rect = rect
        self.props = props
        self.hover = False
        self.pressed = False

    @property
    def text(self) -> str:
        t = str(self.props.get('text', '') or '')
        return t

    @property
    def quickkey(self) -> Optional[int]:
        q = self.props.get('quickkey', None)
        return int(q) if isinstance(q, int) else None

    @property
    def grayed(self) -> bool:
        g = self.props.get('grayedout', 0)
        active = self.props.get('active', 1)
        return bool(g) or (int(active) == 0)


# ----------------------------
# Renderer
# ----------------------------

class GuiRenderer:
    def __init__(self, gui_tree: Dict[str, Any]):
        self.gui_tree = gui_tree
        self.root_common = gui_tree.get('GADGET0', {}).get('COMMON', {})
        self.controls: List[Control] = []
        self.focus_name: Optional[str] = None
        self.window_size = self._get_window_size()
        self._build_controls()

    def _get_window_size(self) -> Tuple[int, int]:
        w = int(self.root_common.get('width', 640) or 640)
        h = int(self.root_common.get('height', 480) or 480)
        return (w, h)

    def _build_controls(self):
        # Determine default focus by name if present
        default_focus = self.gui_tree.get('GADGET0', {}).get('defaultfocus', None)
        if isinstance(default_focus, str) and default_focus:
            self.focus_name = default_focus

        # Collect gadget sections beyond GADGET0
        for key, section in self.gui_tree.items():
            if not key.startswith('GADGET'):
                continue
            if key == 'GADGET0':
                continue
            if not isinstance(section, dict):
                continue

            common = section.get('COMMON', {})
            try:
                ctype = int(common.get('id', 0) or 0)
                name = str(common.get('name', '') or '')
                x = int(common.get('xpos', 0) or 0)
                y = int(common.get('ypos', 0) or 0)
                w = int(common.get('width', 0) or 0)
                h = int(common.get('height', 0) or 0)
            except Exception:
                continue

            # Handle centering sentinels: -1 center, -2 center with 0x80 offset (approximate)
            sw, sh = self.window_size
            if x in (-1, -2):
                x = (sw - w) // 2
                if x == -2:
                    x += 0x80
            if y in (-1, -2):
                y = (sh - h) // 2
                if y == -2:
                    y += 0x80

            rect = pygame.Rect(x, y, w, h)

            # Flatten non-COMMON keys as props
            props = {k: v for k, v in section.items() if k != 'COMMON'}
            # Carry 'active' so we can gray out disabled entries
            try:
                props['active'] = int(common.get('active', 1) or 1)
            except Exception:
                props['active'] = 1
            # Promote multi-line text arrays to a single string with newlines; split on '|' variants later
            if isinstance(props.get('text'), list):
                props['text'] = '\n'.join(str(s) for s in props['text'])

            ctrl = Control(ctype=ctype, name=name, rect=rect, props=props)
            self.controls.append(ctrl)


        # Stable order by name for determinism
        self.controls.sort(key=lambda c: c.name)

    def draw(self, screen: pygame.Surface, font: pygame.font.Font):
        # Clear background
        screen.fill((12, 12, 16))

        for c in self.controls:
            # Colors
            if c.ctype == 5:  # LABEL per observed files (id=5)
                self._draw_label(screen, font, c)
            else:
                # Treat non-label as button-esque for MVP
                self._draw_button(screen, font, c)

    def _draw_label(self, screen: pygame.Surface, font: pygame.font.Font, c: Control):
        text = c.text
        if not text:
            return
        color = (220, 220, 220)
        # Split by newlines; within each line, take token before '|' for MVP
        y = c.rect.y
        for line in str(text).split('\n'):
            token = line.split('|', 1)[0]
            if not token:
                y += font.get_linesize()
                continue
            surf = font.render(token, True, color)
            screen.blit(surf, (c.rect.x, y))
            y += font.get_linesize()

    def _draw_button(self, screen: pygame.Surface, font: pygame.font.Font, c: Control):
        # Basic states
        base = (60, 80, 120)
        hover = (85, 120, 180)
        down = (40, 60, 95)
        disabled = (70, 70, 70)

        if c.grayed:
            fill = disabled
        elif c.pressed:
            fill = down
        elif c.hover or (self.focus_name and c.name.lower() == self.focus_name.lower()):
            fill = hover
        else:
            fill = base

        pygame.draw.rect(screen, fill, c.rect, border_radius=4)
        pygame.draw.rect(screen, (20, 25, 35), c.rect, width=2, border_radius=4)

        # Text centered
        txt = c.text or c.name
        text_color = (255, 255, 255) if not c.grayed else (180, 180, 180)
        if txt:
            surf = font.render(txt, True, text_color)
            tx = c.rect.x + (c.rect.w - surf.get_width()) // 2
            ty = c.rect.y + (c.rect.h - surf.get_height()) // 2
            screen.blit(surf, (tx, ty))

    def update_hover(self, mouse_pos: Tuple[int, int]):
        for c in self.controls:
            c.hover = c.rect.collidepoint(mouse_pos)

    def press_at(self, mouse_pos: Tuple[int, int]) -> Optional[Control]:
        for c in self.controls:
            if c.rect.collidepoint(mouse_pos) and not c.grayed:
                c.pressed = True
                return c
        return None

    def release(self) -> Optional[Control]:
        activated: Optional[Control] = None
        for c in self.controls:
            if c.pressed:
                if c.hover and not c.grayed:
                    activated = c
                c.pressed = False
        return activated

    def activate_quickkey(self, key_event: pygame.event.Event) -> Optional[Control]:
        # quickkey is ASCII code (e.g., 83 for 'S') in files
        if key_event.key is None:
            return None
        uni = key_event.unicode or ''
        if not uni:
            return None
        code = ord(uni.upper())
        for c in self.controls:
            if c.quickkey and c.quickkey == code and not c.grayed:
                return c
        return None


# ----------------------------
# Main
# ----------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: pygame_gui_mvp.py <path/to/.GUI>")
        print("Example: pygame_gui_mvp.py extracted_by_go/guis/MAINMENU.GUI")
        sys.exit(1)

    gui_path = Path(sys.argv[1])
    if not gui_path.exists():
        print(f"Error: {gui_path} not found")
        sys.exit(1)

    gui_tree = parse_tdf_gui(gui_path)
    renderer = GuiRenderer(gui_tree)

    pygame.init()
    pygame.display.set_caption(f"TA GUI MVP - {gui_path.name}")
    screen = pygame.display.set_mode(renderer.window_size)
    clock = pygame.time.Clock()
    # Use a readable default font; later we can map TA .FNT
    font = pygame.font.SysFont("Arial", 16)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEMOTION:
                renderer.update_hover(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                renderer.press_at(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                activated = renderer.release()
                if activated:
                    print(f"Activated: {activated.name} (type={activated.ctype})")
            elif event.type == pygame.KEYDOWN:
                activated = renderer.activate_quickkey(event)
                if activated:
                    print(f"Quickkey: {activated.name} (type={activated.ctype})")

        renderer.draw(screen, font)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
