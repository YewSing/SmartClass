import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import { navigationRef } from './navigationRef'
import ToastContainer from '../components/Toast'
import ModalRouter from '../components/Modals'
import RecordedBanner from '../components/RecordedBanner'
import { C } from '../theme'

// ─── Screens ──────────────────────────────────────────────────────────────────
import Login from '../screens/Login'
import Home from '../screens/Home'
import Attendance from '../screens/Attendance'
import AttSessionDetail from '../screens/AttSessionDetail'
import AttReportStatus from '../screens/AttReportStatus'
import Participation from '../screens/Participation'
import PartSessionPerf from '../screens/PartSessionPerf'
import QuizList from '../screens/QuizList'
import TakeQuiz from '../screens/TakeQuiz'
import QuizResult from '../screens/QuizResult'
import Profile from '../screens/Profile'
import Assistant from '../screens/Assistant'
import AssistantPdf from '../screens/AssistantPdf'
import Flashcards from '../screens/Flashcards'
import Practice from '../screens/Practice'
import Analytics from '../screens/Analytics'
import FaceEnrolment from '../screens/FaceEnrolment'
import FaceConsent from '../screens/FaceConsent'
import FaceCapture from '../screens/FaceCapture'

const Stack = createNativeStackNavigator()
const Tab   = createBottomTabNavigator()

// ─── Stacks ───────────────────────────────────────────────────────────────────

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="HomeScreen" component={Home} />
      <Stack.Screen name="ProfileScreen" component={Profile} />
      <Stack.Screen name="FaceEnrolment" component={FaceEnrolment} />
      <Stack.Screen name="FaceConsent"   component={FaceConsent} />
      <Stack.Screen name="FaceCapture"   component={FaceCapture} />
      <Stack.Screen name="AttSessionDetail" component={AttSessionDetail} />
      <Stack.Screen name="Participation" component={Participation} />
    </Stack.Navigator>
  )
}

function AttendanceStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="AttendanceScreen"  component={Attendance} />
      <Stack.Screen name="AttSessionDetail"  component={AttSessionDetail} />
      <Stack.Screen name="AttReportStatus"   component={AttReportStatus} />
    </Stack.Navigator>
  )
}

function QuizStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="QuizListScreen" component={QuizList} />
      <Stack.Screen name="TakeQuiz"    component={TakeQuiz} />
      <Stack.Screen name="QuizResult"  component={QuizResult} />
    </Stack.Navigator>
  )
}

function AssistantStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="AssistantScreen" component={Assistant} />
      <Stack.Screen name="AssistantPdf"    component={AssistantPdf} />
      <Stack.Screen name="Flashcards"      component={Flashcards} />
      <Stack.Screen name="Practice"        component={Practice} />
    </Stack.Navigator>
  )
}

function AnalyticsStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="AnalyticsScreen" component={Analytics} />
    </Stack.Navigator>
  )
}

// ─── Main tabs ────────────────────────────────────────────────────────────────

const TAB_ICONS = {
  Home:        { active: 'home',                inactive: 'home-outline' },
  Attendance:  { active: 'calendar',            inactive: 'calendar-outline' },
  Quiz:        { active: 'help-circle',         inactive: 'help-circle-outline' },
  Assistant:   { active: 'sparkles',            inactive: 'sparkles-outline' },
  Analytics:   { active: 'bar-chart',           inactive: 'bar-chart-outline' },
}

function MainTabs() {
  const { bottom } = useSafeAreaInsets()
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarShowLabel: true,
        tabBarActiveTintColor: C.primary,
        tabBarInactiveTintColor: C.textHint,
        tabBarStyle: {
          backgroundColor: C.card,
          borderTopWidth: 1,
          borderTopColor: C.border,
          paddingBottom: 4 + bottom,
          height: 74 + bottom,
        },
        tabBarLabelPosition: 'below-icon',
        tabBarLabelStyle: {
          fontSize: 10,
          fontWeight: '600',
          textAlign: 'center',
          marginTop: 2,
        },
        tabBarIcon: ({ focused, color, size }) => {
          const icons = TAB_ICONS[route.name]
          const iconName = focused ? icons.active : icons.inactive
          return <Ionicons name={iconName} size={size} color={color} />
        },
      })}
    >
      <Tab.Screen name="Home"          component={HomeStack}          options={{ title: 'Home' }} />
      <Tab.Screen name="Attendance"    component={AttendanceStack}    options={{ title: 'Attendance', tabBarTestID: 'tab-attendance' }} />
      <Tab.Screen name="Quiz"          component={QuizStack}          options={{ title: 'Quiz', tabBarTestID: 'tab-quiz' }} />
      <Tab.Screen name="Assistant"     component={AssistantStack}     options={{ title: 'Assistant' }} />
      <Tab.Screen name="Analytics"     component={AnalyticsStack}     options={{ title: 'Analytics' }} />
    </Tab.Navigator>
  )
}

// ─── Login stack ──────────────────────────────────────────────────────────────

function LoginStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Login" component={Login} />
    </Stack.Navigator>
  )
}

// ─── Root navigator ───────────────────────────────────────────────────────────

export default function AppNavigator() {
  const { state } = useStudent()

  return (
    <NavigationContainer ref={navigationRef}>
      {state.isLoggedIn ? <MainTabs /> : <LoginStack />}
      {state.isLoggedIn ? <RecordedBanner /> : null}
      <ToastContainer />
      <ModalRouter />
    </NavigationContainer>
  )
}
