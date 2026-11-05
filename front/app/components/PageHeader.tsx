"use client"
import { ReactNode } from 'react'

export default function PageHeader({
  icon, title, subtitle, actions,
}: {
  icon: ReactNode
  title: string
  subtitle?: string
  iconClass?: string
  accentBgClass?: string
  actions?: ReactNode
}) {
  return (
    <header className="page-header-unified">
      <div className="page-header-icon" aria-hidden="true">{icon}</div>
      <div className="page-header-copy">
        <p className="page-header-kicker">BOSS 直聘 · 本机工作台</p>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {actions && <div className="page-header-actions">{actions}</div>}
    </header>
  )
}
