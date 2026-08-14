import axios from 'axios'

const BASE = 'http://127.0.0.1:8123'
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzg2MzgyNzM3LCJpYXQiOjE3ODYzODE4MzcsImp0aSI6IjY5NWQxOWE4ZWQyZTQ5NWFhYTI4MmYwMDMzMWVhODEwIiwidXNlcl9pZCI6MX0.mA4TpnRI1oTQiQ4bJx12K2-5pcfEZoakmDFzDrBlDUc'

// Instance WITHOUT the application/json default (the proposed fix)
const api = axios.create({
  baseURL: BASE,
  headers: { Authorization: `Bearer ${TOKEN}` },
  timeout: 20000,
})

function tinyPng() {
  const b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  return Buffer.from(b64, 'base64')
}

async function main() {
  // JSON object still gets content-type application/json?
  try {
    const r = await api.patch('/api/v1/catalog/admin/products/7/', { name: 'Alphonso Mango' })
    console.log('JSON patch ->', r.status, 'sent CT auto-applied, ok:', r.data && r.data.name === 'Alphonso Mango')
  } catch (e) {
    console.log('JSON patch -> ERROR', e.response ? e.response.status : e.message)
  }

  // FormData upload
  const fd = new FormData()
  fd.append('image', new Blob([tinyPng()], { type: 'image/png' }), 'green.png')
  fd.append('is_primary', 'true')
  try {
    const r = await api.post('/api/v1/catalog/admin/products/7/images/', fd)
    console.log('FormData upload ->', r.status, JSON.stringify(r.data).slice(0, 140))
  } catch (e) {
    console.log('FormData upload -> ERROR', e.response ? e.response.status : e.message,
      e.response ? JSON.stringify(e.response.data).slice(0, 200) : '')
  }
}

main()
