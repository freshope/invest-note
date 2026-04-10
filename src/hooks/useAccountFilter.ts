'use client'

import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'invest-note:account-filter'

export function useAccountFilter() {
  const [selectedAccountId, setSelectedAccountIdState] = useState<string>('all')

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) setSelectedAccountIdState(stored)
  }, [])

  const setSelectedAccountId = useCallback((id: string) => {
    localStorage.setItem(STORAGE_KEY, id)
    setSelectedAccountIdState(id)
  }, [])

  return { selectedAccountId, setSelectedAccountId }
}
