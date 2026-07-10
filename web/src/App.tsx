import { Navigate, Route, Routes } from 'react-router-dom'
import { getRole } from './lib/api/client'
import { StudentLayout } from './routes/student/StudentLayout'
import { JoinPage } from './routes/student/JoinPage'
import { AvailabilityPage } from './routes/student/AvailabilityPage'
import { SurveyPage } from './routes/student/SurveyPage'
import { MyGroupPage } from './routes/student/MyGroupPage'
import { StubPage } from './routes/student/StubPage'
import { InstructorLayout } from './routes/instructor/InstructorLayout'
import { LoginPage } from './routes/instructor/LoginPage'
import { ForgotPasswordPage } from './routes/instructor/ForgotPasswordPage'
import { ResetPasswordPage } from './routes/instructor/ResetPasswordPage'
import { LandingPage } from './routes/instructor/LandingPage'
import { ClassesPage } from './routes/instructor/ClassesPage'
import { DashboardPage } from './routes/instructor/DashboardPage'
import { ConfigPage } from './routes/instructor/ConfigPage'
import { ReviewPage } from './routes/instructor/ReviewPage'
import { PublishPage } from './routes/instructor/PublishPage'
import { HelpPage } from './routes/instructor/HelpPage'

function Home() {
  const role = getRole()
  if (role === 'student') return <Navigate to="/s/availability" replace />
  if (role === 'instructor') return <Navigate to="/i/classes" replace />
  return <LandingPage />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/join" element={<JoinPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      <Route path="/s" element={<StudentLayout />}>
        <Route index element={<Navigate to="availability" replace />} />
        <Route path="availability" element={<AvailabilityPage />} />
        <Route path="survey" element={<SurveyPage />} />
        <Route path="group" element={<MyGroupPage />} />
        <Route path="dashboard" element={<StubPage title="Dashboard" />} />
        <Route path="tasks" element={<StubPage title="Tasks" />} />
        <Route path="profile" element={<StubPage title="Profile" />} />
      </Route>

      <Route path="/i" element={<InstructorLayout />}>
        <Route index element={<Navigate to="classes" replace />} />
        <Route path="classes" element={<ClassesPage />} />
        <Route path="classes/:classId" element={<DashboardPage />} />
        <Route path="classes/:classId/config" element={<ConfigPage />} />
        <Route path="classes/:classId/review" element={<ReviewPage />} />
        <Route path="classes/:classId/publish" element={<PublishPage />} />
        <Route path="help" element={<HelpPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
