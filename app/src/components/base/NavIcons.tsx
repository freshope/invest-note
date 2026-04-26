import type { ReactNode, SVGProps } from "react";

type NavIconProps = SVGProps<SVGSVGElement> & {
  size?: number;
};

function NavIcon({
  size = 24,
  children,
  ...props
}: NavIconProps & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      {...props}
    >
      {children}
    </svg>
  );
}

export function NavHomeIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <g transform="translate(1.8 1.8) scale(.85)">
        <path
          fill="currentColor"
          fillRule="evenodd"
          clipRule="evenodd"
          d="M10.058 1.713a3 3 0 0 1 3.884 0l7 5.999A3 3 0 0 1 22 10v9a3 3 0 0 1-3 3H5a3 3 0 0 1-3-3v-9a3 3 0 0 1 1.058-2.288l7-5.999ZM8.25 13.35c0-.55.45-1 1-1h5.5c.55 0 1 .45 1 1V22h-7.5v-8.65Z"
        />
        <path fill="currentColor" d="M9.75 13.85h4.5V22h-4.5v-8.15Z" />
      </g>
    </NavIcon>
  );
}

export function NavRecordsIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path
        fill="currentColor"
        fillRule="evenodd"
        clipRule="evenodd"
        d="M6.5 3.4c-1.21 0-2.2.99-2.2 2.2v12.8c0 1.21.99 2.2 2.2 2.2h11c1.21 0 2.2-.99 2.2-2.2V9.18c0-.58-.23-1.14-.64-1.55l-3.59-3.59a2.2 2.2 0 0 0-1.55-.64H6.5Zm7.22 1.78v2.96c0 .8.64 1.44 1.44 1.44h2.96l-4.4-4.4ZM7.35 12.7c0-.5.4-.9.9-.9h7.5a.9.9 0 1 1 0 1.8h-7.5a.9.9 0 0 1-.9-.9Zm0 3.55c0-.5.4-.9.9-.9h5.8a.9.9 0 1 1 0 1.8h-5.8a.9.9 0 0 1-.9-.9Z"
      />
    </NavIcon>
  );
}

export function NavAnalysisIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path
        fill="currentColor"
        d="M5.2 13.25c0-.66.54-1.2 1.2-1.2h1.8c.66 0 1.2.54 1.2 1.2v5.95c0 .66-.54 1.2-1.2 1.2H6.4c-.66 0-1.2-.54-1.2-1.2v-5.95Z"
      />
      <path
        fill="currentColor"
        d="M10.25 8.6c0-.66.54-1.2 1.2-1.2h1.8c.66 0 1.2.54 1.2 1.2v10.6c0 .66-.54 1.2-1.2 1.2h-1.8c-.66 0-1.2-.54-1.2-1.2V8.6Z"
      />
      <path
        fill="currentColor"
        d="M15.3 4.8c0-.66.54-1.2 1.2-1.2h1.8c.66 0 1.2.54 1.2 1.2v14.4c0 .66-.54 1.2-1.2 1.2h-1.8c-.66 0-1.2-.54-1.2-1.2V4.8Z"
      />
    </NavIcon>
  );
}

export function NavSettingsIcon(props: NavIconProps) {
  return (
    <NavIcon {...props}>
      <path
        fill="currentColor"
        fillRule="evenodd"
        clipRule="evenodd"
        d="M9.67 4.14a2.34 2.34 0 0 1 4.66 0 2.34 2.34 0 0 0 3.32 1.91 2.34 2.34 0 0 1 2.33 4.04 2.34 2.34 0 0 0 0 3.82 2.34 2.34 0 0 1-2.33 4.04 2.34 2.34 0 0 0-3.32 1.91 2.34 2.34 0 0 1-4.66 0 2.34 2.34 0 0 0-3.32-1.91 2.34 2.34 0 0 1-2.33-4.04 2.34 2.34 0 0 0 0-3.82 2.34 2.34 0 0 1 2.33-4.04 2.34 2.34 0 0 0 3.32-1.91ZM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
      />
    </NavIcon>
  );
}
