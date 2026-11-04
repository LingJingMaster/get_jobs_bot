'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { BriefcaseBusiness, CheckSquare2, FileText, FlaskConical, Gauge, ListChecks, Moon, Settings2, Sun } from 'lucide-react'
import { useTheme } from 'next-themes'
import { API_BASE } from '@/lib/api'

const nav = [
  { href: '/', label: '工作台', icon: Gauge },
  { href: '/boss', label: '1 档案与事实', icon: FileText },
  { href: '/boss', label: '2 岗位采集', icon: ListChecks },
  { href: '/boss/analysis', label: '3 岗位与匹配', icon: CheckSquare2 },
  { href: '/ai-config', label: '4 材料工作台', icon: BriefcaseBusiness },
  { href: '/boss', label: '5 申请跟踪', icon: FlaskConical },
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
      {nav.map(({ href, label, icon: Icon }) => <Link key={label} href={href} className={pathname === href ? 'nav-item active' : 'nav-item'}><Icon size={16} /><span>{label}</span></Link>)}
      <p className="nav-label tools-label">工具</p>
      <Link href="/boss/analysis" className={pathname === '/boss/analysis' ? 'nav-item active' : 'nav-item'}><ListChecks size={16} /><span>标注与实验</span></Link>
      <Link href="/env-config" className={pathname === '/env-config' ? 'nav-item active' : 'nav-item'}><Settings2 size={16} /><span>设置与状态</span></Link>
    </nav>
    <div className="sidebar-footer"><div className="connection"><i className={health ? 'online' : ''} />{health ? '服务在线' : '等待后端'}</div><button className="theme-button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} {theme === 'dark' ? '浅色界面' : '深色界面'}</button><small>仅支持 Boss 直聘 · v1.0</small></div>
  </aside>
}
