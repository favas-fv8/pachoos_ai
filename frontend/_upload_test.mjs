import axios from 'axios'

const BASE = 'http://127.0.0.1:8123'
const jsonApi = axios.create({
  baseURL: BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 20000,
})

async function login() {
  const res = await axios.post(`${BASE}/api/v1/auth/admin/login/`, {
    email: 'super_admin@pachoos.local',
    password: 'adminpass123',
  })
  return res.data.access
}

function tinyPng() {
  const b64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
  return Buffer.from(b64, 'base64')
}

async function main() {
  const token = await login()
  jsonApi.defaults.headers.Authorization = `Bearer ${token}`

  const fd = new FormData()
  fd.append('image', new Blob([tinyPng()], { type: 'image/png' }), 't.png')
  fd.append('is_primary', 'true')

  // Approach A: rely on default (application/json) - EXPECT FAILURE
  try {
    const r = await jsonApi.post('/api/v1/catalog/admin/products/7/images/', fd)
    console.log('A default-json  ->', r.status, JSON.stringify(r.data).slice(0, 120))
  } catch (e) {
    console.log('A default-json  -> ERROR', e.response ? e.response.status : e.message,
      e.response ? JSON.stringify(e.response.data).slice(0, 160) : '')
  }

  // Approach B: explicit multipart/form-data
  try {
    const r = await jsonApi.post('/api/v1/catalog/admin/products/7/images/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    console.log('B explicit mp   ->', r.status, JSON.stringify(r.data).slice(0, 120))
  } catch (e) {
    console.log('B explicit mp   -> ERROR', e.response ? e.response.status : e.message,
      e.response ? JSON.stringify(e.response.data).slice(0, 160) : '')
  }
}

main()
