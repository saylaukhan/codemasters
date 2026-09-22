import { theme, type ThemeConfig } from 'antd'

// Ant Design theme from the DESIGN.md v2 tokens (front matter `antd-theme`). AntD derives its
// shades from these literals, so the values repeat tokens.css: the second and last place in
// web/ where hex is allowed. Keep both files in step (ADR-015).

interface Palette {
  accent: string
  accentHover: string
  accentPressed: string
  accentSoft: string
  textOnAccent: string
  bgPage: string
  bgSurface: string
  bgSubtle: string
  bgSelected: string
  border: string
  borderStrong: string
  textPrimary: string
  textSecondary: string
  textMuted: string
  textLink: string
  error: string
  warning: string
  success: string
  shadowDropdown: string
}

const lightPalette: Palette = {
  accent: '#2E6BE6',
  accentHover: '#2559C9',
  accentPressed: '#1F4FB8',
  accentSoft: '#EAF0FE',
  textOnAccent: '#FFFFFF',
  bgPage: '#F5F7FA',
  bgSurface: '#FFFFFF',
  bgSubtle: '#F0F3F7',
  bgSelected: '#EAF0FE',
  border: 'rgba(23, 29, 38, 0.06)',
  borderStrong: 'rgba(23, 29, 38, 0.14)',
  textPrimary: '#171D26',
  textSecondary: '#5B6472',
  textMuted: '#8B94A1',
  textLink: '#2E6BE6',
  error: '#DC3F44',
  warning: '#E0900F',
  success: '#1A9E5C',
  shadowDropdown: '0 8px 24px rgba(23, 29, 38, 0.12)',
}

const darkPalette: Palette = {
  accent: '#5B8DFF',
  accentHover: '#7AA3FF',
  accentPressed: '#9DBBFF',
  accentSoft: 'rgba(91, 141, 255, 0.16)',
  textOnAccent: '#0F1115',
  bgPage: '#0F1115',
  bgSurface: '#171A20',
  bgSubtle: '#262B33',
  bgSelected: 'rgba(91, 141, 255, 0.16)',
  border: 'rgba(255, 255, 255, 0.08)',
  borderStrong: 'rgba(255, 255, 255, 0.14)',
  textPrimary: '#E8ECF1',
  textSecondary: '#A3ABB8',
  textMuted: '#8A93A1',
  textLink: '#5B8DFF',
  error: '#F0555A',
  warning: '#F0A62A',
  success: '#2FBF72',
  shadowDropdown: '0 8px 24px rgba(0, 0, 0, 0.45)',
}

function buildTheme(palette: Palette, algorithm: ThemeConfig['algorithm']): ThemeConfig {
  return {
    algorithm,
    cssVar: true,
    hashed: false,
    token: {
      colorPrimary: palette.accent,
      colorPrimaryHover: palette.accentHover,
      colorPrimaryActive: palette.accentPressed,
      colorPrimaryBg: palette.accentSoft,
      colorTextLightSolid: palette.textOnAccent,
      borderRadius: 10,
      borderRadiusLG: 12,
      borderRadiusSM: 6,
      fontFamily: 'Manrope, Onest, Inter, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
      fontFamilyCode: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      fontSize: 14,
      controlHeight: 38,
      controlHeightSM: 32,
      controlHeightLG: 44,
      colorBgLayout: palette.bgPage,
      colorBgContainer: palette.bgSurface,
      colorBorder: palette.borderStrong,
      colorBorderSecondary: palette.border,
      colorText: palette.textPrimary,
      colorTextSecondary: palette.textSecondary,
      colorTextTertiary: palette.textMuted,
      colorLink: palette.textLink,
      colorError: palette.error,
      colorWarning: palette.warning,
      colorSuccess: palette.success,
      boxShadowSecondary: palette.shadowDropdown,
      motionDurationFast: '0.12s',
      motionDurationMid: '0.15s',
      motionDurationSlow: '0.15s',
      motionEaseOut: 'ease-out',
    },
    components: {
      Card: { borderRadiusLG: 16 },
      Modal: { borderRadiusLG: 16 },
      // Header and side navigation sit on the page background, without lines (DESIGN.md §2.2).
      Layout: {
        headerHeight: 64,
        headerPadding: '0 24px',
        headerBg: palette.bgPage,
        siderBg: palette.bgPage,
        bodyBg: palette.bgPage,
        triggerBg: palette.bgPage,
        triggerColor: palette.textSecondary,
      },
      // Side navigation, DESIGN.md §3.6: 38px items, radius 10, 12px from the edges.
      Menu: {
        itemBg: 'transparent',
        itemHeight: 38,
        itemBorderRadius: 10,
        itemMarginInline: 12,
        itemColor: palette.textPrimary,
        itemHoverBg: palette.bgSubtle,
        itemSelectedBg: palette.bgSelected,
        itemSelectedColor: palette.accentPressed,
        iconSize: 18,
        collapsedIconSize: 18,
        collapsedWidth: 64,
        activeBarBorderWidth: 0,
      },
      // Table, DESIGN.md §3.12: header without a fill, hairline rows, no vertical lines.
      Table: {
        headerBg: 'transparent',
        headerColor: palette.textMuted,
        headerSplitColor: 'transparent',
        borderColor: palette.border,
        rowHoverBg: palette.bgSubtle,
        rowSelectedBg: palette.bgSelected,
        rowSelectedHoverBg: palette.bgSelected,
        cellPaddingBlock: 14,
      },
    },
  }
}

export const lightTheme = buildTheme(lightPalette, theme.defaultAlgorithm)
export const darkTheme = buildTheme(darkPalette, theme.darkAlgorithm)

// Sizes that AntD and lucide take as numbers, not CSS (DESIGN.md §2.2, §3.0, §3.20, §3.21).
export const SIZES = {
  siderWidth: 232,
  siderCollapsedWidth: 64,
  iconSm: 16,
  iconNav: 18,
  iconMd: 20,
  iconEmpty: 48,
  iconStroke: 1.75,
  drawerWidth: 480,
} as const

/** Width at which the side navigation collapses to icons with tooltips (DESIGN.md §9.3). */
export const COMPACT_SCREEN = '(max-width: 1279px)'

/** Width at which the side navigation leaves the page for a drawer in the header (inclusive). */
export const NARROW_SCREEN = '(max-width: 1024px)'

/** Width at which tables become card lists and the page action sticks to the bottom (inclusive). */
export const PHONE_SCREEN = '(max-width: 768px)'
