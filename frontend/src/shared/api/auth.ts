import { api } from './client'
import type { Employee, TokenResponse } from './types'

export function login(loginName: string, pin: string): Promise<TokenResponse> {
  return api<TokenResponse>('/auth/login', {
    method: 'POST',
    json: { login: loginName, pin },
  })
}

export function fetchMe(): Promise<Employee> {
  return api<Employee>('/auth/me')
}
