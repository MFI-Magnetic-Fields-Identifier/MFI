import { useState, type FormEvent } from 'react'
import { photoAccept, predictPhoto, type Prediction, type PredictionStatus } from './predict'

type UploadState =
  | { state: 'idle' | 'pending' }
  | { state: 'error'; message: string }
  | { state: 'result'; prediction: Prediction }

const statusLabels: Record<PredictionStatus, string> = {
  accepted: 'Candidato principal disponível',
  needs_confirmation: 'Identificação requer confirmação',
  unknown: 'Identificação inconclusiva',
}
const scoreFormat = new Intl.NumberFormat('pt-BR', { style: 'percent', maximumFractionDigits: 1 })

export function PhotoIdentification() {
  const [photo, setPhoto] = useState<File | null>(null)
  const [upload, setUpload] = useState<UploadState>({ state: 'idle' })
  const pending = upload.state === 'pending'

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!photo || pending) return

    setUpload({ state: 'pending' })
    try {
      const prediction = await predictPhoto(photo)
      setUpload({ state: 'result', prediction })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Não foi possível analisar a foto.'
      setUpload({ state: 'error', message })
    }
  }

  return (
    <section className="identification" aria-labelledby="identification-heading">
      <h2 id="identification-heading">Identificar por foto</h2>
      <form onSubmit={submit} aria-busy={pending}>
        <div className="upload-controls">
          <div>
            <label htmlFor="motor-photo">Foto do motor</label>
            <input
              id="motor-photo"
              type="file"
              accept={photoAccept}
              aria-describedby="photo-hint"
              disabled={pending}
              onChange={(event) => {
                setPhoto(event.currentTarget.files?.[0] ?? null)
                setUpload({ state: 'idle' })
              }}
            />
            <p id="photo-hint">JPEG, PNG ou WebP · até 8 MiB</p>
          </div>
          <button type="submit" disabled={!photo || pending}>Enviar foto</button>
        </div>
      </form>

      <div aria-live="polite" aria-atomic="true">
        {pending && <p className="upload-feedback">Analisando a foto…</p>}
        {upload.state === 'error' && <p className="upload-feedback upload-error">{upload.message}</p>}
        {upload.state === 'result' && (
          <div className="upload-feedback">
            <p className="prediction-status">{statusLabels[upload.prediction.status]}</p>
            <ol className="candidates" aria-label="Candidatos sugeridos">
              {upload.prediction.candidates.map((candidate) => (
                <li key={candidate.model_id}>
                  <span>{candidate.model_id}</span>
                  <strong>{scoreFormat.format(candidate.score)}</strong>
                </li>
              ))}
            </ol>
            <p className="score-note">Pontuações do classificador, sem calibração probabilística.</p>
          </div>
        )}
      </div>
    </section>
  )
}
