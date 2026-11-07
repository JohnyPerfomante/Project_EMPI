import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query'
import { lazy, StrictMode, Suspense, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Navigate, Route, Routes, useNavigate } from 'react-router-dom'
import { Layout } from './components/layout'
import { Empty, QueryState } from './components/ui'
import { AuditLog, Catalog, Settings, Users } from './features/admin'
import { Login } from './features/auth'
import { CourseDetail, Courses } from './features/courses'
import { NewQuestion, QuestionDetail, Questions } from './features/questions'
import { Register } from './features/registration'
import { SubmissionDetail, Submissions } from './features/submissions'
import { VariationDetail, Variations } from './features/variations'
import { ApiError, api } from './lib/api'
import type { User } from './lib/types'
import './styles/main.css'

const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 10_000 } } })
const authKey = ['session']
const Dashboard = lazy(() => import('./features/dashboard').then(module => ({ default: module.Dashboard })))

function App() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const session = useQuery({ queryKey: authKey, queryFn: async () => {
    try { return await api<User>('/auth/me') }
    catch (error) {
      if (error instanceof ApiError && error.status === 401) return null
      throw error
    }
  }, staleTime: 60_000 })
  useEffect(() => {
    const signedOut = () => { queryClient.clear(); queryClient.setQueryData(authKey, null); navigate('/login', { replace: true }) }
    window.addEventListener('empi:signed-out', signedOut)
    return () => window.removeEventListener('empi:signed-out', signedOut)
  }, [navigate, queryClient])
  if (session.isPending || session.isError) return <main className="boot"><QueryState pending={session.isPending} error={session.error}/>
    {session.isError && <button className="button secondary" onClick={() => session.refetch()}>Спробувати ще раз</button>}</main>
  if (!session.data) return <Routes>
    <Route path="register" element={<Register/>}/>
    <Route path="*" element={<Login onLogin={user => {
      queryClient.clear(); queryClient.setQueryData(authKey, user); navigate('/', { replace: true })
    }}/>}/>
  </Routes>
  const user = session.data
  const staff = user.role !== 'student'
  const admin = user.role === 'admin'
  return <Routes>
    <Route element={<Layout user={user} logout={async () => {
      await api('/auth/logout', 'POST'); queryClient.clear(); queryClient.setQueryData(authKey, null); navigate('/login', { replace: true })
    }}/>}>
      <Route index element={<Suspense fallback={<QueryState pending error={null}/>}><Dashboard/></Suspense>}/>
      <Route path="login" element={<Navigate to="/" replace/>}/>
      <Route path="register" element={<Navigate to="/" replace/>}/>
      <Route path="courses" element={<Courses/>}/>
      <Route path="courses/:id" element={<CourseDetail/>}/>
      <Route path="questions" element={<Questions/>}/>
      <Route path="questions/new" element={staff ? <NewQuestion/> : <Navigate to="/questions" replace/>}/>
      <Route path="questions/:id" element={<QuestionDetail/>}/>
      <Route path="submissions" element={<Submissions/>}/>
      <Route path="submissions/:id" element={<SubmissionDetail/>}/>
      {staff && <><Route path="variations" element={<Variations/>}/><Route path="variations/:id" element={<VariationDetail/>}/></>}
      {admin && <>
        <Route path="admin/users" element={<Users/>}/>
        <Route path="admin/catalog" element={<Catalog/>}/>
        <Route path="admin/settings" element={<Settings/>}/>
        <Route path="admin/audit" element={<AuditLog/>}/>
      </>}
      <Route path="*" element={<><Empty text="Сторінка відсутня або недоступна."/><Link className="button secondary" to="/">До огляду</Link></>}/>
    </Route>
  </Routes>
}

createRoot(document.getElementById('root')!).render(<StrictMode>
  <QueryClientProvider client={client}><BrowserRouter><App/></BrowserRouter></QueryClientProvider>
</StrictMode>)
