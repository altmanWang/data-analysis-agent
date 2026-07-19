import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from '../stores/chatStore.js'
import ChatPanel from '../components/ChatPanel.vue'

// jsdom polyfill: scrollIntoView not implemented
Element.prototype.scrollIntoView = vi.fn()

// Mock websocket to avoid connection attempts
vi.mock('../utils/websocket', () => ({
  createWS: () => ({ send: vi.fn(), close: vi.fn(), readyState: 1 })
}))

// Mock stores to avoid HTTP calls during mount
vi.mock('../stores/sessionStore', () => ({
  useSessionStore: () => ({
    currentId: null,
    pendingInput: null,
    fetchSession: vi.fn().mockResolvedValue({ title: 'Test Session', status: 'active' }),
    createSession: vi.fn().mockResolvedValue({ session_id: 'new-session' }),
  })
}))

vi.mock('../stores/fileStore', () => ({
  useFileStore: () => ({
    tree: [],
    fetchTree: vi.fn(),
    upload: vi.fn(),
  })
}))

describe('ChatPanel v3 rendering', () => {
  let wrapper, chatStore

  beforeEach(() => {
    setActivePinia(createPinia())
    chatStore = useChatStore()
    const routerMock = {
      push: vi.fn(),
      currentRoute: { value: { params: { id: 'test-session' } } }
    }
    wrapper = mount(ChatPanel, {
      props: { id: 'test-session' },
      global: {
        stubs: { 'router-link': true },
        mocks: { $router: routerMock },
      }
    })
  })

  afterEach(() => {
    wrapper.unmount()
  })

  // ==========================================================
  // SkillBar tests
  // ==========================================================
  it('renders skill loading bar when msg.role is skill with status loading', async () => {
    chatStore.setSkillLoading('ui-ux-pro-max')
    await wrapper.vm.$nextTick()
    const skillBar = wrapper.find('.skill-bar')
    expect(skillBar.exists()).toBe(true)
    expect(skillBar.text()).toContain('ui-ux-pro-max')
    expect(skillBar.classes()).toContain('loading')
  })

  it('renders skill loaded bar when msg.role is skill with status loaded', async () => {
    chatStore.setSkillLoading('ui-ux-pro-max')
    chatStore.setSkillLoaded('ui-ux-pro-max')
    await wrapper.vm.$nextTick()
    const skillBar = wrapper.find('.skill-bar')
    expect(skillBar.classes()).toContain('loaded')
    expect(skillBar.text()).toContain('ui-ux-pro-max')
  })

  // ==========================================================
  // SubagentCard tests
  // ==========================================================
  it('renders subagent card when msg.role is subagent', async () => {
    chatStore.addSubagent('data-analyst')
    await wrapper.vm.$nextTick()
    const subCard = wrapper.find('.subagent-card')
    expect(subCard.exists()).toBe(true)
    expect(subCard.text()).toContain('data-analyst')
  })

  it('shows correct status indicator for running subagent', async () => {
    chatStore.addSubagent('data-analyst')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.subagent-card').classes()).toContain('running')
  })

  it('updates status when subagent completes', async () => {
    chatStore.addSubagent('data-analyst')
    chatStore.finishSubagent('data-analyst', 'completed')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.subagent-card').classes()).toContain('completed')
  })

  // ==========================================================
  // Tool calls under subagent
  // ==========================================================
  it('renders tool calls inside subagent card when source matches', async () => {
    chatStore.addSubagent('data-analyst')
    chatStore.addToolCall('subagent:data-analyst', 'load_csv', '{"file_path":"/data.csv"}')
    chatStore.addToolCall('coordinator', 'read_file', '{"file_path":"/config.json"}')
    await wrapper.vm.$nextTick()
    const toolCards = wrapper.findAll('.tool-card')
    expect(toolCards.length).toBeGreaterThanOrEqual(2)
  })

  // ==========================================================
  // Backward compatibility: old messages still render
  // ==========================================================
  it('still renders user messages correctly', async () => {
    chatStore.addMessage({ role: 'user', content: 'Hello' })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.message-row.user').exists()).toBe(true)
    expect(wrapper.text()).toContain('Hello')
  })

  it('still renders assistant markdown', async () => {
    chatStore.appendContent('coordinator', '**Analysis** result')
    await wrapper.vm.$nextTick()
    expect(wrapper.html()).toContain('<strong>Analysis</strong>')
  })
})
