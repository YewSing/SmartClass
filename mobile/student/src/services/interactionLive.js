import { connectStudentLive } from './live'

export const connectInteractionLive = ({ baseUrl, getToken, refreshToken, onEvent }) =>
  connectStudentLive({ baseUrl, getToken, refreshToken, onEvent })
