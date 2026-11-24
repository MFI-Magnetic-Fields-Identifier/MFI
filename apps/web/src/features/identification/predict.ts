const photoTypes = {
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  png: 'image/png',
  webp: 'image/webp',
}
const acceptedTypes = new Set(Object.values(photoTypes))
export const photoAccept = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
const maxPhotoBytes = 8 * 1024 * 1024

export type PredictionStatus = 'accepted' | 'needs_confirmation' | 'unknown'

type Candidate = {
  model_id: string
  score: number
}

export type Prediction = {
  candidates: Candidate[]
  status: PredictionStatus
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isCandidate(value: unknown): value is Candidate {
  return record(value) && typeof value.model_id === 'string' && value.model_id.trim() !== ''
    && typeof value.score === 'number' && value.score >= 0 && value.score <= 1
}

function isPrediction(value: unknown): value is Prediction {
  return record(value)
    && (value.status === 'accepted' || value.status === 'needs_confirmation' || value.status === 'unknown')
    && Array.isArray(value.candidates) && value.candidates.length > 0
    && value.candidates.every(isCandidate)
}

export async function predictPhoto(photo: File): Promise<Prediction> {
  if (photo.size === 0 || photo.size > maxPhotoBytes) {
    throw new Error('Selecione uma foto não vazia de até 8 MiB.')
  }
  const extension = photo.name.split('.').at(-1)?.toLowerCase()
  const fallback = Object.entries(photoTypes).find(([key]) => key === extension)?.[1]
  const contentType = photo.type || fallback
  if (!contentType || !acceptedTypes.has(contentType)) {
    throw new Error('Selecione uma foto JPEG, PNG ou WebP.')
  }

  let response: Response
  try {
    response = await fetch('/predict', {
      method: 'POST',
      headers: { 'Content-Type': contentType },
      body: photo,
      signal: AbortSignal.timeout(30_000),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new Error('A previsão demorou mais de 30 segundos. Tente novamente.')
    }
    throw new Error('Não foi possível conectar à API de identificação.')
  }

  const result: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = record(result) && typeof result.detail === 'string' ? result.detail : null
    throw new Error(detail || 'A API de identificação está indisponível. Tente novamente.')
  }
  if (!isPrediction(result)) {
    throw new Error('A API retornou uma previsão inválida.')
  }
  return result
}
