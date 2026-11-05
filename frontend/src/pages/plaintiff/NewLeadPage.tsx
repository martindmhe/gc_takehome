import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { createLead, getMeta, type LeadCreate } from '@/lib/api'
import { useSession } from '@/lib/session'

export function NewLeadPage() {
  const { user } = useSession()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const meta = useQuery({ queryKey: ['meta'], queryFn: getMeta, staleTime: Infinity })

  const [form, setForm] = useState<LeadCreate>({
    contact_name: user?.display_name ?? '',
    contact_email: user?.email ?? '',
    region: '',
    category: '',
    description: '',
  })

  const submit = useMutation({
    mutationFn: createLead,
    onSuccess: (lead) => {
      queryClient.setQueryData(['lead', lead.id], lead)
      void queryClient.invalidateQueries({ queryKey: ['leads'] })
      navigate(`/plaintiff/leads/${lead.id}`)
    },
  })

  function set<K extends keyof LeadCreate>(key: K, value: LeadCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    submit.mutate(form)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Submit a lead</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="grid gap-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="contact_name">Name</Label>
              <Input
                id="contact_name"
                required
                maxLength={200}
                value={form.contact_name}
                onChange={(e) => set('contact_name', e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="contact_email">Email</Label>
              <Input
                id="contact_email"
                type="email"
                required
                maxLength={320}
                value={form.contact_email}
                onChange={(e) => set('contact_email', e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="region">Region</Label>
              <Input
                id="region"
                required
                maxLength={50}
                list="region-options"
                placeholder="e.g. California"
                value={form.region}
                onChange={(e) => set('region', e.target.value)}
              />
              <datalist id="region-options">
                {meta.data?.regions.map((r) => (
                  <option key={r.value} value={r.label} />
                ))}
              </datalist>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="category">Category</Label>
              <Select
                name="category"
                required
                value={form.category}
                onValueChange={(value) => set('category', value)}
                disabled={!meta.isSuccess}
              >
                <SelectTrigger id="category" className="w-full">
                  <SelectValue placeholder={meta.isPending ? 'Loading…' : 'Select a category'} />
                </SelectTrigger>
                <SelectContent>
                  {meta.data?.categories.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="description">Describe your situation</Label>
            <Textarea
              id="description"
              required
              maxLength={5000}
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
            />
          </div>

          {meta.isError && (
            <p className="text-destructive text-sm">Couldn't load categories: {meta.error.message}</p>
          )}
          {submit.isError && (
            <p role="alert" className="text-destructive text-sm">
              {submit.error.message}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" asChild>
              <Link to="/plaintiff">Cancel</Link>
            </Button>
            <Button type="submit" disabled={submit.isPending || !meta.isSuccess}>
              {submit.isPending ? 'Submitting…' : 'Submit lead'}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
