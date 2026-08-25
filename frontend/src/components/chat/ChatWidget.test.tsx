// ChatWidget audience routing — the signed-in user's role must decide which
// backend assistant handles the conversation, on every page:
//   admin roles  -> /api/v1/ai/admin-chat/  (never stripped to a guest)
//   customers    -> /api/v1/ai/chat/
//   guests       -> /api/v1/ai/chat/
import { describe, expect, it, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import authReducer, { type AuthState } from '@/store/slices/authSlice'
import uiReducer from '@/store/slices/uiSlice'
import { ChatWidget } from '@/components/chat/ChatWidget'

const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }))
vi.mock('@/lib/api/client', () => ({
  api: { post: postMock },
}))

function makeAuth(overrides: Partial<AuthState> = {}): AuthState {
  return {
    access: null,
    refresh: null,
    user: null,
    isAuthenticated: false,
    isLoading: false,
    ...overrides,
  }
}

function makeStore(auth: AuthState) {
  return configureStore({
    reducer: { auth: authReducer, ui: uiReducer },
    preloadedState: { auth },
  })
}

function makeUser(role: string): AuthState['user'] {
  return { id: 1, full_name: 'Test User', role, is_verified: true }
}

async function sendMessage(store = makeStore(makeAuth())) {
  render(
    <Provider store={store}>
      <ChatWidget />
    </Provider>,
  )
  fireEvent.click(screen.getByRole('button', { name: /assistant/i }))
  const input = screen.getByRole('textbox')
  fireEvent.change(input, { target: { value: 'cart products' } })
  // The send button is icon-only (no accessible name) — submit via Enter.
  fireEvent.keyDown(input, { key: 'Enter' })
  await waitFor(() => expect(postMock).toHaveBeenCalledTimes(1))
}

beforeAll(() => {
  // jsdom does not implement scrolling.
  Element.prototype.scrollIntoView = vi.fn()
})

afterEach(() => {
  postMock.mockReset()
})

describe('ChatWidget audience routing', () => {
  it.each(['super_admin', 'store_manager'])(
    'routes an authenticated %s to the admin endpoint',
    async (role) => {
      postMock.mockResolvedValue({ data: { response: '**Recent orders** table' } })
      await sendMessage(
        makeStore(
          makeAuth({
            access: 'a',
            refresh: 'r',
            user: makeUser(role),
            isAuthenticated: true,
          }),
        ),
      )
      expect(screen.getByText('PACHOOS Admin Assistant')).toBeInTheDocument()
      const [url, payload] = postMock.mock.calls[0]
      expect(url).toBe('/api/v1/ai/admin-chat/')
      expect(payload.message).toBe('cart products')
      expect(payload).not.toHaveProperty('location')
    },
  )

  it('routes an authenticated customer to the customer endpoint', async () => {
    postMock.mockResolvedValue({ data: { response: 'hello' } })
    await sendMessage(
      makeStore(
        makeAuth({
          access: 'a',
          refresh: 'r',
          user: makeUser('customer'),
          isAuthenticated: true,
        }),
      ),
    )
    expect(screen.getByText('PACHOOS Assistant')).toBeInTheDocument()
    const [url, payload] = postMock.mock.calls[0]
    expect(url).toBe('/api/v1/ai/chat/')
    expect(payload).toHaveProperty('location')
  })

  it('keeps guests on the customer endpoint', async () => {
    postMock.mockResolvedValue({ data: { response: 'hello' } })
    await sendMessage()
    const [url] = postMock.mock.calls[0]
    expect(url).toBe('/api/v1/ai/chat/')
  })
})
