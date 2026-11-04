"use client"
import { ReactNode } from 'react'
export default function ContentArea({ children }: { children: ReactNode }) {
  return <main className="desk-content"><div className="desk-content-inner">{children}</div></main>
}
