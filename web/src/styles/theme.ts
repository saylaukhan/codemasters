import { theme, type ThemeConfig } from 'antd'

// Ant Design theme from the DESIGN.md tokens (front matter `antd-theme`). AntD derives its
// shades from these literals, so the values repeat tokens.css: the second and last place in
// web/ where hex is allowed. Keep both files in step.

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
}

const lightPalette: Palette = {
  accent: '#1DB866',
  accentHover: '#17A35A',
  accentPressed: '#128C4C',
  accentSoft: '#E6F7EE',
  textOnAccent: '#FFFFFF',
  bgPage: '#F5F6F7',
  bgSurface: '#FFFFFF',
  bgSubtle: '#EFF1F3',
  bgSelected: '#E6F7EE',
  border: '#E3E5E8',
  borderStrong: '#C9CDD2',
  textPrimary: '#1F2328',
  textSecondary: '#5F6670',
  textMuted: '#9AA0A8',
  textLink: '#1F6FD1',
}

const darkPalette: Palette = {
  accent: '#2BC775',
  accentHover: '#4AD68B',
  accentPressed: '#5FE09B',
  accentSoft: '#173A28',
  textOnAccent: '#141619',
  bgPage: '#141619',
  bgSurface: '#1E2125',
  bgSubtle: '#272B30',
  bgSelected: '#173A28',
  border: '#33383E',
  borderStrong: '#4A5057',
  textPrimary: '#EDEFF2',
  textSecondary: '#A4ABB3',
  textMuted: '#6F767E',
  textLink: '#4C9AFF',
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
      borderRadius: 6,
      borderRadiusLG: 8,
      borderRadiusSM: 4,
      fontFamily: 'Inter, Onest, Manrope, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
      fontFamilyCode: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
      fontSize: 14,
      controlHeight: 36,
      controlHeightSM: 28,
      controlHeightLG: 44,
      colorBgLayout: palette.bgPage,
      colorBgContainer: palette.bgSurface,
      colorBorder: palette.borderStrong,
      colorBorderSecondary: palette.border,
      colorText: palette.textPrimary,
      colorTextSecondary: palette.textSecondary,
      colorTextTertiary: palette.textMuted,
      colorLink: palette.textLink,
      colorError: '#E5484D',
      colorWarning: '#F5A300',
      colorSuccess: '#1DB866',
      boxShadowSecondary: '0 4px 16px rgba(0, 0, 0, 0.08)',
      motionDurationFast: '0.12s',
      motionDurationMid: '0.15s',
      motionDurationSlow: '0.15s',
      motionEaseOut: 'ease-out',
    },
    components: {
      Card: { borderRadiusLG: 12 },
      Modal: { borderRadiusLG: 16 },
      Layout: {
        headerHeight: 56,
        headerPadding: '0 24px',
        headerBg: palette.bgSurface,
        siderBg: palette.bgPage,
        bodyBg: palette.bgPage,
        triggerBg: palette.bgPage,
        triggerColor: palette.textSecondary,
      },
      // Side navigation, DESIGN.md §3.6: 36px items, radius 6, 8px from the edges.
      Menu: {
        itemBg: 'transparent',
        itemHeight: 36,
        itemBorderRadius: 6,
        itemMarginInline: 8,
        itemColor: palette.textPrimary,
        itemHoverBg: palette.bgSubtle,
        itemSelectedBg: palette.bgSelected,
        itemSelectedColor: palette.accentPressed,
        iconSize: 20,
        collapsedIconSize: 20,
        collapsedWidth: 56,
        activeBarBorderWidth: 0,
      },
    },
  }
}

export const lightTheme = buildTheme(lightPalette, theme.defaultAlgorithm)
export const darkTheme = buildTheme(darkPalette, theme.darkAlgorithm)

// Sizes that AntD and lucide take as numbers, not CSS (DESIGN.md §2.2, §3.0, §3.21).
export const SIZES = {
  siderWidth: 240,
  siderCollapsedWidth: 56,
  iconSm: 16,
  iconMd: 20,
  iconEmpty: 48,
  iconStroke: 1.5,
} as const

/** Width at which the side navigation collapses and the padding shrinks (inclusive). */
export const NARROW_SCREEN = '(max-width: 1024px)'
