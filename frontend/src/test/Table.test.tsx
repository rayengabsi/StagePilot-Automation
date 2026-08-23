import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Table from '../components/Table'

describe('Table', () => {
  it('renders column headers when rows exist', () => {
    render(<Table columns={['Name', 'Score']} rows={[['a', 'b']]} />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Score')).toBeInTheDocument()
  })

  it('renders rows', () => {
    render(<Table columns={['A', 'B']} rows={[['x', 'y']]} />)
    expect(screen.getByText('x')).toBeInTheDocument()
    expect(screen.getByText('y')).toBeInTheDocument()
  })

  it('shows empty message when no rows', () => {
    render(<Table columns={['A']} rows={[]} empty="Nothing here" />)
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
  })

  it('shows default empty message', () => {
    render(<Table columns={['A']} rows={[]} />)
    expect(screen.getByText('No data')).toBeInTheDocument()
  })
})
