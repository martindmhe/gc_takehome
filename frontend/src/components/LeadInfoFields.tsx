import type { ReactNode } from 'react'

import type { LeadInfo } from '@/lib/api'

export function DetailItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </div>
  )
}

/** The plaintiff-provided part of a lead. `children` adds extra items at the top. */
export function LeadInfoFields({ lead, children }: { lead: LeadInfo; children?: ReactNode }) {
  return (
    <div className="space-y-6">
      <dl className="grid gap-4 text-sm sm:grid-cols-2">
        {children}
        <DetailItem label="Submitted">{new Date(lead.created_at).toLocaleString()}</DetailItem>
        <DetailItem label="Category / region">
          {lead.category_label} · {lead.region_label}
        </DetailItem>
        <DetailItem label="Contact name">{lead.contact_name}</DetailItem>
        <DetailItem label="Contact email">
          <a className="underline-offset-4 hover:underline" href={`mailto:${lead.contact_email}`}>
            {lead.contact_email}
          </a>
        </DetailItem>
      </dl>
      <div className="text-sm">
        <h2 className="text-muted-foreground mb-1">Description</h2>
        <p className="whitespace-pre-wrap">{lead.description}</p>
      </div>
    </div>
  )
}
