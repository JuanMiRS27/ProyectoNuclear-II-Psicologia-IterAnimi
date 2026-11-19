import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import { Icon, type IconName } from './Icon'

type Variant = 'primary' | 'secondary' | 'quiet' | 'danger' | 'danger-solid'
type Size = 'md' | 'sm'

function classes(variant: Variant, size: Size, extra?: string) {
  return ['btn', `btn-${variant}`, size === 'sm' ? 'btn-sm' : '', extra ?? ''].filter(Boolean).join(' ')
}

interface CommonProps {
  variant?: Variant
  size?: Size
  icon?: IconName
  children: ReactNode
}

/** Botón con estado de envío: deshabilita y anuncia mientras la acción está en curso. */
export function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  pending,
  pendingLabel,
  children,
  className,
  type = 'button',
  disabled,
  ...rest
}: CommonProps & ButtonHTMLAttributes<HTMLButtonElement> & { pending?: boolean; pendingLabel?: string }) {
  return (
    <button
      type={type}
      className={classes(variant, size, className)}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
      {...rest}
    >
      {icon && <Icon name={icon} size={size === 'sm' ? 16 : 18} />}
      {pending && pendingLabel ? pendingLabel : children}
    </button>
  )
}

export function ButtonLink({ variant = 'secondary', size = 'md', icon, children, className, ...rest }: CommonProps & LinkProps) {
  return (
    <Link className={classes(variant, size, className)} {...rest}>
      {icon && <Icon name={icon} size={size === 'sm' ? 16 : 18} />}
      {children}
    </Link>
  )
}
