import http from 'k6/http'
import { check, sleep } from 'k6'

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
  },
}

export default function () {
  const baseUrl = __ENV.BASE_URL || 'http://localhost:8000'
  const headers = __ENV.API_KEY ? { 'X-API-Key': __ENV.API_KEY } : {}

  const health = http.get(`${baseUrl}/health`, { headers })
  check(health, { 'health responds 200': (response) => response.status === 200 })

  const policy = http.get(`${baseUrl}/api/v1/privacy-policy`, { headers })
  check(policy, { 'privacy policy responds 200': (response) => response.status === 200 })

  sleep(1)
}
