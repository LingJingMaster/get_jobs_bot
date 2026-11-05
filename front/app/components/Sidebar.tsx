'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { FileText, Gauge, ListChecks, Moon, Send, Settings2, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { API_BASE } from '@/lib/api'

const nav = [
  { href: '/', label: '工作台', icon: Gauge },
  { href: '/boss', label: '1 采集岗位 JD', icon: ListChecks },
  { href: '/resume', label: '2 优化简历', icon: FileText },
  { href: '/delivery', label: '3 投递与沟通', icon: Send },
]

export default function Sidebar() {
  const pathname = usePathname()
  const { theme, setTheme } = useTheme()
  const [health, setHealth] = useState(false)
  useEffect(() => {
    const check = () => fetch(`${API_BASE}/api/health`).then(r => setHealth(r.ok)).catch(() => setHealth(false))
    check(); const timer = setInterval(check, 30000); return () => clearInterval(timer)
  }, [])
  return <aside className="desk-sidebar">
    <div className="sidebar-brand"><span className="brand-mark">B</span><div><strong>Get Jobs</strong><small>本机求职工作台</small></div></div>
    <nav className="sidebar-nav">
      <p className="nav-label">求职流程</p>
      {nav.map(({ href, label, icon: Icon }) => <Link key={label} href={href} className={pathname.replace(/\/$/, '') === href.replace(/\/$/, '') ? 'nav-item active' : 'nav-item'}><Icon size={16} /><span>{label}</span></Link>)}
      <p className="nav-label tools-label">设置</p>
      <Link href="/env-config" className={pathname.replace(/\/$/, '') === '/env-config' ? 'nav-item active' : 'nav-item'}><Settings2 size={16} /><span>AI 与服务设置</span></Link>
    </nav>
    <div className="sidebar-footer"><div className="connection"><i className={health ? 'online' : ''} />{health ? '服务在线' : '等待后端'}</div><button className="theme-button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} {theme === 'dark' ? '浅色界面' : '深色界面'}</button><small>仅支持 Boss 直聘 · v1.0</small></div>
  </aside>
}
