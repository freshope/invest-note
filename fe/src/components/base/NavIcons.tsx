import type { ComponentType, SVGProps } from "react";
import {
  ChartBarIcon as ChartBarIconOutline,
  Cog6ToothIcon as Cog6ToothIconOutline,
  DocumentTextIcon as DocumentTextIconOutline,
  HomeIcon as HomeIconOutline,
} from "@heroicons/react/24/outline";
import {
  ChartBarIcon as ChartBarIconSolid,
  Cog6ToothIcon as Cog6ToothIconSolid,
  DocumentTextIcon as DocumentTextIconSolid,
  HomeIcon as HomeIconSolid,
} from "@heroicons/react/24/solid";

type HeroIcon = ComponentType<SVGProps<SVGSVGElement>>;

type NavIconProps = SVGProps<SVGSVGElement> & {
  active: boolean;
  size?: number;
};

function createNavIcon(OutlineIcon: HeroIcon, SolidIcon: HeroIcon) {
  return function NavIcon({ active, size = 24, ...props }: NavIconProps) {
    const Icon = active ? SolidIcon : OutlineIcon;

    return (
      <Icon
        aria-hidden="true"
        focusable="false"
        width={size}
        height={size}
        {...props}
      />
    );
  };
}

export const NavHomeIcon = createNavIcon(HomeIconOutline, HomeIconSolid);
export const NavRecordsIcon = createNavIcon(
  DocumentTextIconOutline,
  DocumentTextIconSolid
);
export const NavAnalysisIcon = createNavIcon(
  ChartBarIconOutline,
  ChartBarIconSolid
);
export const NavSettingsIcon = createNavIcon(
  Cog6ToothIconOutline,
  Cog6ToothIconSolid
);
