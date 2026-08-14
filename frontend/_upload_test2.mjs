import axios from 'axios'

const BASE = 'http://127.0.0.1:8123'
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzg2MzgyNzM3LCJpYXQiOjE3ODYzODE4MzcsImp0aSI6IjY5NWQxOWE4ZWQyZTQ5NWFhYTI4MmYwMDMzMWVhODEwIiwidXNlcl9pZCI6MX0.mA4TpnRI1oTQiQ4bJx12K2-5pcfEZoakmDFzDrBlDUc'

const jsonApi = axios.create({
  baseURL: BASE,
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${TOKEN}` },
  timeout: 20000,
})

function tinyPng() {
  const b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  return Buffer.from(b64, 'base64')
}

async function main() {
  // fresh FormData each attempt
  function fd() {
    const f = new FormData()
    f.append('image', new Blob([tinyPng()], { type: 'image/png' }), 't.png')
    f.append('is_primary', 'true')
    return f
  }

  try {
    const r = await jsonApi.post('/api/v1/catalog/admin/products/7/images/', fd())
    console.log('A default-json ->', r.status, JSON.stringify(r.data).slice(0, 140))
  } catch (e) {
    console.log('A default-json -> ERROR', e.response ? e.response.status : e.message,
      e.response ? JSON.stringify(e.response.data).slice(0, 200) : '')
  }

  try {
    const r = await jsonApi.post('/api/v1/catalog/admin/products/7/images/', fd(), {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    console.log('B explicit-mp  ->', r.status, JSON.stringify(r.data).slice(0, 140))
  } catch (e) {
    console.log('B explicit-mp  -> ERROR', e.response ? e.response.status : e.message,
      e.response ? JSON.stringify(e.response.data).slice(0, 200) : '')
  }

  try {
    const r = await jsonApi.post('/api/v1/catalog/admin/products/7/images/', fd(), {
      headers: { 'Content-Type': undefined },
    })
    console.log('C undefined-ct ->', r.status, JSON.stringify(r.data).slice(0, 140))
  } catch (e) {
    console.log('C undefined-ct -> ERROR', e.response ? e.response.status : e.message,
      e.response ? JSON.stringify(e.response.data).slice(0, 200) : '')
  }
}

main()
