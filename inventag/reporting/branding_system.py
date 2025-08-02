#!/usr/bin/env python3
"""
Advanced Branding and Styling Customization System

Comprehensive branding system with logo placement options, color scheme customization,
font styling, page layout options, and conditional formatting themes.

Features:
- Logo placement options (header, footer, cover page, watermark)
- Color scheme customization for charts, tables, and highlights
- Font family and styling options for professional document appearance
- Custom page layout options (margins, spacing, orientation)
- Conditional formatting themes for compliance status visualization
"""

import logging
import os
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from abc import ABC, abstractmethod
from enum import Enum
import colorsys

from .document_generator import BrandingConfig


class LogoPosition(Enum):
    """Logo placement positions."""
    HEADER_LEFT = "header_left"
    HEADER_CENTER = "header_center"
    HEADER_RIGHT = "header_right"
    FOOTER_LEFT = "footer_left"
    FOOTER_CENTER = "footer_center"
    FOOTER_RIGHT = "footer_right"
    COVER_PAGE = "cover_page"
    WATERMARK = "watermark"


class PageOrientation(Enum):
    """Page orientation options."""
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class PageSize(Enum):
    """Standard page sizes."""
    LETTER = "letter"
    A4 = "a4"
    LEGAL = "legal"
    TABLOID = "tabloid"
    A3 = "a3"


@dataclass
class LogoConfiguration:
    """Logo configuration with placement and sizing options."""
    enabled: bool = False
    logo_path: Optional[str] = None
    positions: List[LogoPosition] = field(default_factory=list)
    size: Tuple[float, float] = (1.0, 0.5)  # width, height in inches
    opacity: float = 1.0  # 0.0 to 1.0
    maintain_aspect_ratio: bool = True
    alignment: str = "left"  # left, center, right
    margin: Tuple[float, float, float, float] = (0.1, 0.1, 0.1, 0.1)  # top, right, bottom, left


@dataclass
class ColorScheme:
    """Comprehensive color scheme configuration."""
    # Primary colors
    primary: str = "#366092"
    secondary: str = "#4472C4"
    accent: str = "#70AD47"
    
    # Status colors
    success: str = "#70AD47"
    warning: str = "#FFC000"
    danger: str = "#C5504B"
    info: str = "#5B9BD5"
    
    # UI colors
    background: str = "#FFFFFF"
    text: str = "#000000"
    border: str = "#D0D0D0"
    
    # Table colors
    header_bg: str = "#366092"
    header_text: str = "#FFFFFF"
    alt_row: str = "#F2F2F2"
    selected_row: str = "#E6F3FF"
    
    # Chart colors
    chart_colors: List[str] = field(default_factory=lambda: [
        "#366092", "#4472C4", "#70AD47", "#FFC000", "#C5504B",
        "#5B9BD5", "#A5A5A5", "#FFC000", "#70AD47", "#264478"
    ])
    
    # Compliance colors
    compliant: str = "#70AD47"
    non_compliant: str = "#C5504B"
    partial_compliant: str = "#FFC000"
    unknown: str = "#A5A5A5"


@dataclass
class FontConfiguration:
    """Font styling configuration."""
    # Font families
    primary_font: str = "Calibri"
    secondary_font: str = "Arial"
    monospace_font: str = "Consolas"
    
    # Font sizes (in points)
    title_size: int = 18
    heading1_size: int = 16
    heading2_size: int = 14
    heading3_size: int = 12
    body_size: int = 11
    table_size: int = 10
    caption_size: int = 9
    
    # Font weights
    title_weight: str = "bold"
    heading_weight: str = "bold"
    body_weight: str = "normal"
    
    # Line spacing
    line_spacing: float = 1.15
    paragraph_spacing: float = 6.0  # points
    
    # Text alignment defaults
    title_alignment: str = "center"
    heading_alignment: str = "left"
    body_alignment: str = "left"


@dataclass
class PageLayoutConfiguration:
    """Page layout and spacing configuration."""
    # Page settings
    orientation: PageOrientation = PageOrientation.PORTRAIT
    size: PageSize = PageSize.LETTER
    
    # Margins (in inches)
    margins: Dict[str, float] = field(default_factory=lambda: {
        "top": 1.0,
        "bottom": 1.0,
        "left": 1.25,
        "right": 1.0
    })
    
    # Header and footer space
    header_margin: float = 0.5
    footer_margin: float = 0.5
    
    # Column settings
    columns: int = 1
    column_spacing: float = 0.5
    
    # Section spacing
    section_spacing: float = 12.0  # points
    subsection_spacing: float = 6.0  # points
    
    # Table settings
    table_margin: float = 6.0  # points
    table_cell_padding: float = 4.0  # points
    table_border_width: float = 0.5  # points
    
    # Page breaks
    avoid_orphans: bool = True
    avoid_widows: bool = True
    keep_with_next: bool = True


@dataclass
class ConditionalFormattingTheme:
    """Conditional formatting theme for compliance status visualization."""
    name: str
    description: str = ""
    
    # Compliance status formatting
    compliant_format: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#E8F5E8",
        "text_color": "#2E7D32",
        "font_weight": "normal",
        "border_color": "#4CAF50"
    })
    
    non_compliant_format: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#FFEBEE",
        "text_color": "#C62828",
        "font_weight": "bold",
        "border_color": "#F44336"
    })
    
    partial_compliant_format: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#FFF8E1",
        "text_color": "#F57C00",
        "font_weight": "normal",
        "border_color": "#FF9800"
    })
    
    unknown_format: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#F5F5F5",
        "text_color": "#616161",
        "font_weight": "normal",
        "border_color": "#9E9E9E"
    })
    
    # Risk level formatting
    high_risk_format: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#FFCDD2",
        "text_color": "#B71C1C",
        "font_weight": "bold",
        "border_color": "#F44336"
    })
    
    medium_risk_format: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#FFE0B2",
        "text_color": "#E65100",
        "font_weight": "normal",
        "border_color": "#FF9800"
    })
    
    low_risk_format: Dict[str, Any] = field(default_factory=lambda: {
        "background_color": "#E8F5E8",
        "text_color": "#1B5E20",
        "font_weight": "normal",
        "border_color": "#4CAF50"
    })


@dataclass
class AdvancedBrandingConfig:
    """Advanced branding configuration with comprehensive customization options."""
    # Basic branding
    company_name: str = "Organization"
    company_tagline: Optional[str] = None
    document_classification: str = "CONFIDENTIAL"
    
    # Logo configuration
    logo: LogoConfiguration = field(default_factory=LogoConfiguration)
    
    # Color scheme
    colors: ColorScheme = field(default_factory=ColorScheme)
    
    # Typography
    fonts: FontConfiguration = field(default_factory=FontConfiguration)
    
    # Page layout
    layout: PageLayoutConfiguration = field(default_factory=PageLayoutConfiguration)
    
    # Conditional formatting themes
    formatting_themes: Dict[str, ConditionalFormattingTheme] = field(default_factory=dict)
    
    # Custom styles
    custom_styles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Watermark settings
    watermark_enabled: bool = False
    watermark_text: str = "CONFIDENTIAL"
    watermark_opacity: float = 0.1
    watermark_rotation: float = -45.0  # degrees


class ColorUtilities:
    """Utilities for color manipulation and generation."""
    
    @staticmethod
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        if len(hex_color) != 6:
            return (0, 0, 0)  # Default to black
        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            return (0, 0, 0)
    
    @staticmethod
    def rgb_to_hex(r: int, g: int, b: int) -> str:
        """Convert RGB values to hex color."""
        return f"#{r:02x}{g:02x}{b:02x}"
    
    @staticmethod
    def lighten_color(hex_color: str, factor: float = 0.2) -> str:
        """Lighten a color by the specified factor (0.0 to 1.0)."""
        r, g, b = ColorUtilities.hex_to_rgb(hex_color)
        h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        l = min(1.0, l + factor)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return ColorUtilities.rgb_to_hex(int(r*255), int(g*255), int(b*255))
    
    @staticmethod
    def darken_color(hex_color: str, factor: float = 0.2) -> str:
        """Darken a color by the specified factor (0.0 to 1.0)."""
        r, g, b = ColorUtilities.hex_to_rgb(hex_color)
        h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        l = max(0.0, l - factor)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return ColorUtilities.rgb_to_hex(int(r*255), int(g*255), int(b*255))
    
    @staticmethod
    def generate_color_palette(base_color: str, count: int = 5) -> List[str]:
        """Generate a color palette based on a base color."""
        colors = []
        r, g, b = ColorUtilities.hex_to_rgb(base_color)
        h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
        
        for i in range(count):
            # Vary the lightness and saturation
            new_l = max(0.2, min(0.8, l + (i - count//2) * 0.15))
            new_s = max(0.3, min(1.0, s + (i - count//2) * 0.1))
            r, g, b = colorsys.hls_to_rgb(h, new_l, new_s)
            colors.append(ColorUtilities.rgb_to_hex(int(r*255), int(g*255), int(b*255)))
        
        return colors
    
    @staticmethod
    def get_contrast_color(hex_color: str) -> str:
        """Get a contrasting color (black or white) for the given color."""
        r, g, b = ColorUtilities.hex_to_rgb(hex_color)
        # Calculate luminance
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#000000" if luminance > 0.5 else "#FFFFFF"


class BrandingThemeManager:
    """Manages branding themes and provides theme operations."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.BrandingThemeManager")
        self._predefined_themes = self._initialize_predefined_themes()
    
    def _initialize_predefined_themes(self) -> Dict[str, AdvancedBrandingConfig]:
        """Initialize predefined branding themes."""
        themes = {}
        
        # Professional Blue Theme
        professional_blue = AdvancedBrandingConfig(
            company_name="Organization",
            colors=ColorScheme(
                primary="#366092",
                secondary="#4472C4",
                accent="#70AD47",
                success="#70AD47",
                warning="#FFC000",
                danger="#C5504B"
            ),
            fonts=FontConfiguration(
                primary_font="Calibri",
                secondary_font="Arial"
            )
        )
        themes["professional_blue"] = professional_blue
        
        # Corporate Green Theme
        corporate_green = AdvancedBrandingConfig(
            company_name="Organization",
            colors=ColorScheme(
                primary="#2E7D32",
                secondary="#4CAF50",
                accent="#8BC34A",
                success="#4CAF50",
                warning="#FF9800",
                danger="#F44336"
            ),
            fonts=FontConfiguration(
                primary_font="Times New Roman",
                secondary_font="Arial"
            )
        )
        themes["corporate_green"] = corporate_green
        
        # Modern Dark Theme
        modern_dark = AdvancedBrandingConfig(
            company_name="Organization",
            colors=ColorScheme(
                primary="#263238",
                secondary="#37474F",
                accent="#00BCD4",
                success="#4CAF50",
                warning="#FF9800",
                danger="#F44336",
                background="#FAFAFA",
                text="#212121",
                header_bg="#263238",
                header_text="#FFFFFF",
                alt_row="#F5F5F5"
            ),
            fonts=FontConfiguration(
                primary_font="Segoe UI",
                secondary_font="Arial"
            )
        )
        themes["modern_dark"] = modern_dark
        
        # High Contrast Theme (for accessibility)
        high_contrast = AdvancedBrandingConfig(
            company_name="Organization",
            colors=ColorScheme(
                primary="#000000",
                secondary="#333333",
                accent="#0066CC",
                success="#008000",
                warning="#FF8C00",
                danger="#CC0000",
                background="#FFFFFF",
                text="#000000",
                border="#000000"
            ),
            fonts=FontConfiguration(
                primary_font="Arial",
                secondary_font="Arial",
                body_size=12,  # Larger for accessibility
                table_size=11
            )
        )
        themes["high_contrast"] = high_contrast
        
        return themes
    
    def get_theme(self, theme_name: str) -> Optional[AdvancedBrandingConfig]:
        """Get a predefined theme by name."""
        return self._predefined_themes.get(theme_name)
    
    def list_themes(self) -> List[str]:
        """List all available predefined themes."""
        return list(self._predefined_themes.keys())
    
    def create_custom_theme(
        self, 
        base_theme: str = "professional_blue",
        **customizations
    ) -> AdvancedBrandingConfig:
        """Create a custom theme based on a predefined theme."""
        base = self._predefined_themes.get(base_theme)
        if not base:
            base = self._predefined_themes["professional_blue"]
        
        # Create a copy of the base theme
        custom_theme = AdvancedBrandingConfig(
            company_name=customizations.get("company_name", base.company_name),
            company_tagline=customizations.get("company_tagline", base.company_tagline),
            document_classification=customizations.get("document_classification", base.document_classification),
            logo=base.logo,
            colors=base.colors,
            fonts=base.fonts,
            layout=base.layout,
            formatting_themes=base.formatting_themes.copy(),
            custom_styles=base.custom_styles.copy(),
            watermark_enabled=customizations.get("watermark_enabled", base.watermark_enabled),
            watermark_text=customizations.get("watermark_text", base.watermark_text),
            watermark_opacity=customizations.get("watermark_opacity", base.watermark_opacity),
            watermark_rotation=customizations.get("watermark_rotation", base.watermark_rotation)
        )
        
        # Apply color customizations
        if "primary_color" in customizations:
            custom_theme.colors.primary = customizations["primary_color"]
            # Generate complementary colors
            palette = ColorUtilities.generate_color_palette(custom_theme.colors.primary, 5)
            custom_theme.colors.secondary = palette[1]
            custom_theme.colors.accent = palette[2]
        
        # Apply font customizations
        if "primary_font" in customizations:
            custom_theme.fonts.primary_font = customizations["primary_font"]
        
        return custom_theme
    
    def create_conditional_formatting_theme(
        self, 
        name: str,
        compliance_colors: Optional[Dict[str, str]] = None,
        risk_colors: Optional[Dict[str, str]] = None
    ) -> ConditionalFormattingTheme:
        """Create a conditional formatting theme."""
        theme = ConditionalFormattingTheme(name=name)
        
        if compliance_colors:
            if "compliant" in compliance_colors:
                theme.compliant_format["background_color"] = ColorUtilities.lighten_color(compliance_colors["compliant"], 0.8)
                theme.compliant_format["text_color"] = ColorUtilities.darken_color(compliance_colors["compliant"], 0.3)
                theme.compliant_format["border_color"] = compliance_colors["compliant"]
            
            if "non_compliant" in compliance_colors:
                theme.non_compliant_format["background_color"] = ColorUtilities.lighten_color(compliance_colors["non_compliant"], 0.8)
                theme.non_compliant_format["text_color"] = ColorUtilities.darken_color(compliance_colors["non_compliant"], 0.3)
                theme.non_compliant_format["border_color"] = compliance_colors["non_compliant"]
        
        if risk_colors:
            if "high_risk" in risk_colors:
                theme.high_risk_format["background_color"] = ColorUtilities.lighten_color(risk_colors["high_risk"], 0.8)
                theme.high_risk_format["text_color"] = ColorUtilities.darken_color(risk_colors["high_risk"], 0.3)
                theme.high_risk_format["border_color"] = risk_colors["high_risk"]
        
        return theme


class BrandingApplicator(ABC):
    """Abstract base class for applying branding to different document formats."""
    
    def __init__(self, branding_config: AdvancedBrandingConfig):
        self.branding = branding_config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def apply_branding(self, document_object: Any) -> Any:
        """Apply branding to the document object."""
        pass
    
    @abstractmethod
    def apply_logo(self, document_object: Any, position: LogoPosition) -> Any:
        """Apply logo at the specified position."""
        pass
    
    @abstractmethod
    def apply_color_scheme(self, document_object: Any) -> Any:
        """Apply color scheme to the document."""
        pass
    
    @abstractmethod
    def apply_fonts(self, document_object: Any) -> Any:
        """Apply font configuration to the document."""
        pass
    
    @abstractmethod
    def apply_conditional_formatting(self, document_object: Any, theme_name: str) -> Any:
        """Apply conditional formatting theme."""
        pass


class BrandingValidator:
    """Validates branding configurations and provides recommendations."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.BrandingValidator")
    
    def validate_branding_config(self, config: AdvancedBrandingConfig) -> List[str]:
        """Validate branding configuration and return list of issues."""
        issues = []
        
        # Validate logo configuration
        if config.logo.enabled and not config.logo.logo_path:
            issues.append("Logo is enabled but no logo path specified")
        
        if config.logo.logo_path and not os.path.exists(config.logo.logo_path):
            issues.append(f"Logo file not found: {config.logo.logo_path}")
        
        # Validate colors
        color_fields = [
            config.colors.primary, config.colors.secondary, config.colors.accent,
            config.colors.success, config.colors.warning, config.colors.danger
        ]
        
        for color in color_fields:
            if not self._is_valid_hex_color(color):
                issues.append(f"Invalid hex color: {color}")
        
        # Validate fonts
        if not config.fonts.primary_font:
            issues.append("Primary font not specified")
        
        # Validate page layout
        if config.layout.margins["top"] < 0.5:
            issues.append("Top margin too small (minimum 0.5 inches recommended)")
        
        if config.layout.margins["bottom"] < 0.5:
            issues.append("Bottom margin too small (minimum 0.5 inches recommended)")
        
        return issues
    
    def _is_valid_hex_color(self, color: str) -> bool:
        """Check if a string is a valid hex color."""
        if not color.startswith('#'):
            return False
        
        hex_part = color[1:]
        if len(hex_part) not in [3, 6]:
            return False
        
        try:
            int(hex_part, 16)
            return True
        except ValueError:
            return False
    
    def get_accessibility_recommendations(self, config: AdvancedBrandingConfig) -> List[str]:
        """Get accessibility recommendations for the branding configuration."""
        recommendations = []
        
        # Check color contrast
        primary_rgb = ColorUtilities.hex_to_rgb(config.colors.primary)
        bg_rgb = ColorUtilities.hex_to_rgb(config.colors.background)
        
        contrast_ratio = self._calculate_contrast_ratio(primary_rgb, bg_rgb)
        if contrast_ratio < 4.5:
            recommendations.append("Primary color contrast ratio is below WCAG AA standard (4.5:1)")
        
        # Check font sizes
        if config.fonts.body_size < 11:
            recommendations.append("Body font size is below recommended minimum (11pt)")
        
        if config.fonts.table_size < 10:
            recommendations.append("Table font size is below recommended minimum (10pt)")
        
        return recommendations
    
    def _calculate_contrast_ratio(self, color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
        """Calculate contrast ratio between two colors."""
        def luminance(rgb):
            r, g, b = [x/255.0 for x in rgb]
            r = r/12.92 if r <= 0.03928 else ((r + 0.055)/1.055) ** 2.4
            g = g/12.92 if g <= 0.03928 else ((g + 0.055)/1.055) ** 2.4
            b = b/12.92 if b <= 0.03928 else ((b + 0.055)/1.055) ** 2.4
            return 0.2126 * r + 0.7152 * g + 0.0722 * b
        
        l1 = luminance(color1)
        l2 = luminance(color2)
        
        if l1 > l2:
            return (l1 + 0.05) / (l2 + 0.05)
        else:
            return (l2 + 0.05) / (l1 + 0.05)


# Factory functions
def create_branding_theme_manager() -> BrandingThemeManager:
    """Create a BrandingThemeManager instance."""
    return BrandingThemeManager()

def create_default_branding_config(
    company_name: str = "Organization",
    theme: str = "professional_blue"
) -> AdvancedBrandingConfig:
    """Create a default branding configuration."""
    manager = BrandingThemeManager()
    config = manager.get_theme(theme)
    if config:
        config.company_name = company_name
        return config
    else:
        return AdvancedBrandingConfig(company_name=company_name)