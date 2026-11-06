import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'

import { Pagination } from '@/components/Pagination'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { downloadDocument, listDocuments, uploadDocument } from '@/lib/api'
import { ROLE_LABELS } from '@/lib/session'

const PAGE_SIZE = 10

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Opens a PDF in a new tab using the browser's own PDF viewer. */
async function openPdf(documentId: string): Promise<void> {
  // Open the tab right away, while we're still in the click handler, so popup
  // blockers allow it; then point it at the downloaded PDF.
  const tab = window.open('', '_blank')
  try {
    const blob = await downloadDocument(documentId)
    const url = URL.createObjectURL(blob)
    if (tab) tab.location.href = url
    else window.location.href = url
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    tab?.close()
    throw error
  }
}

/**
 * A lead's shared documents with an upload control. Shown on lead and case pages
 * (a case's documents are its lead's). The server decides who may see or add them.
 */
export function DocumentsPanel({ leadId }: { leadId: string }) {
  const queryClient = useQueryClient()
  const fileInput = useRef<HTMLInputElement>(null)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const documents = useQuery({
    queryKey: ['documents', leadId, { offset, limit: PAGE_SIZE }],
    queryFn: () => listDocuments(leadId, { offset, limit: PAGE_SIZE }),
    placeholderData: keepPreviousData,
  })

  const upload = useMutation({
    mutationFn: (file: File) => uploadDocument(leadId, file),
    onSuccess: () => {
      setOffset(0)
      void queryClient.invalidateQueries({ queryKey: ['documents', leadId] })
    },
    onError: (e) => setError(e.message),
  })

  function onFileChosen(file: File | undefined) {
    if (fileInput.current) fileInput.current.value = '' // allow choosing the same file again
    if (!file) return
    setError(null)
    // A quick check for a helpful message; the server validates the real content.
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError(`"${file.name}" isn't a PDF. Only PDF files can be uploaded.`)
      return
    }
    upload.mutate(file)
  }

  function onOpen(documentId: string) {
    setError(null)
    openPdf(documentId).catch((e: Error) => setError(e.message))
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="text-lg">Documents</CardTitle>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={(e) => onFileChosen(e.target.files?.[0])}
        />
        <Button
          variant="outline"
          disabled={upload.isPending}
          onClick={() => fileInput.current?.click()}
        >
          {upload.isPending ? 'Uploading…' : 'Upload PDF'}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-muted-foreground text-sm">
          Shared between the plaintiff and the assigned firm. PDF only, up to 10 MB.
        </p>

        {error && (
          <p role="alert" className="text-destructive text-sm">
            {error}
          </p>
        )}

        {documents.isPending && <p className="text-muted-foreground">Loading…</p>}
        {documents.isError && <p className="text-destructive">{documents.error.message}</p>}

        {documents.isSuccess && documents.data.items.length === 0 && (
          <p className="text-muted-foreground rounded-md border p-6 text-center text-sm">
            No documents yet.
          </p>
        )}

        {documents.isSuccess && documents.data.items.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Uploaded by</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead className="text-right">Size</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.data.items.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="max-w-64 truncate">
                    <button
                      type="button"
                      className="text-left font-medium underline-offset-4 hover:underline"
                      title={`Open ${d.original_filename}`}
                      onClick={() => onOpen(d.id)}
                    >
                      {d.original_filename}
                    </button>
                  </TableCell>
                  <TableCell>
                    {d.uploaded_by.display_name}{' '}
                    <span className="text-muted-foreground">
                      ({ROLE_LABELS[d.uploaded_by.role]})
                    </span>
                  </TableCell>
                  <TableCell>{new Date(d.created_at).toLocaleString()}</TableCell>
                  <TableCell className="text-right">{formatSize(d.size_bytes)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        <Pagination
          offset={offset}
          pageSize={PAGE_SIZE}
          total={documents.data?.total ?? 0}
          onChange={setOffset}
        />
      </CardContent>
    </Card>
  )
}
