import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Table from '../components/Table'

describe('Table', () => {
  it('renders column headers', () => {
    render(<Table columns={['Name', 'Score']} rows={[]} />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Score')).toBeInTheDocument()
  })

  it('renders rows', () => {
    render(<Table columns={['A', 'B']} rows={[['x', 'y']]} />)
    expect(screen.getByText('x')).toBeInTheDocument()
    expect(screen.getByText('y')).toBeInTheDocument()
  })

  it('shows empty message', () => {
    render(<Table columns={['A']} rows={[]} empty="Nothing here" />)
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
  })
})
