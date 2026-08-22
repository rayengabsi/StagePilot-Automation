import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatCard from '../components/StatCard'

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard label="Jobs" value={42} />)
    expect(screen.getByText('Jobs')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders hint when provided', () => {
    render(<StatCard label="Status" value="Running" hint="Since 2pm" />)
    expect(screen.getByText('Since 2pm')).toBeInTheDocument()
  })

  it('renders string value', () => {
    render(<StatCard label="Health" value="ok" />)
    expect(screen.getByText('ok')).toBeInTheDocument()
  })
})
