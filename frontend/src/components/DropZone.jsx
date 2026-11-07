import { useRef, useState } from 'react'
import { cn } from '../lib/cn'

export default function DropZone({ label, sublabel, file, onFile, onRemove, disabled = false }) {
  const inputRef = useRef(null)
  const [hover, setHover] = useState(false)

  function handleFiles(fileList) {
    const picked = fileList?.[0]
    if (picked) onFile(picked)
  }

  function handleRemove(e) {
    e.stopPropagation()
    if (inputRef.current) inputRef.current.value = ''
    onRemove?.()
  }

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-mist-300">{label}</span>
        {sublabel && <span className="text-[11px] text-mist-500">{sublabel}</span>}
      </div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && !disabled && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          if (!disabled) setHover(true)
        }}
        onDragLeave={() => setHover(false)}
        onDrop={(e) => {
          e.preventDefault()
          setHover(false)
          if (!disabled) handleFiles(e.dataTransfer.files)
        }}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-6 text-center transition-colors',
          disabled ? 'cursor-not-allowed opacity-50 border-navy-700' : 'cursor-pointer',
          !disabled && hover && 'border-cyan-glow bg-cyan-glow/5',
          !disabled && !hover && 'border-navy-600 bg-navy-850 hover:border-navy-400',
        )}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          className={cn('h-6 w-6', hover ? 'text-cyan-glow' : 'text-navy-400')}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 8.25 12 3.75m0 0L7.5 8.25M12 3.75v12.75"
          />
        </svg>
        {file ? (
          <div className="flex max-w-full items-center gap-2">
            <p className="truncate font-mono text-xs text-mist-100">{file.name}</p>
            {!disabled && onRemove && (
              <button
                type="button"
                onClick={handleRemove}
                aria-label={`Remove ${file.name}`}
                className="shrink-0 rounded-full p-0.5 text-mist-500 transition-colors hover:bg-danger/10 hover:text-danger"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="h-3.5 w-3.5"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        ) : (
          <p className="text-xs text-mist-500">
            Drag &amp; drop, or <span className="text-cyan-glow">browse</span>
          </p>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".tif,.tiff,.png,image/tiff,image/png"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
    </div>
  )
}
