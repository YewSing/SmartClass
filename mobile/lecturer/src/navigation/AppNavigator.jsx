import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useLecturer } from '../context/LecturerContext'
import { navigationRef } from './navigationRef'
import ToastContainer from '../components/Toast'
import ModalRouter from '../components/Modals'
import { C } from '../theme'

// ─── Screens ──────────────────────────────────────────────────────────────────
import Login from '../screens/Login'
import Dashboard from '../screens/Dashboard'
import Profile from '../screens/Profile'
import AttendanceSessions from '../screens/AttendanceSessions'
import AttendanceDetail from '../screens/AttendanceDetail'
import QuizList from '../screens/QuizList'
import CreateQuiz from '../screens/CreateQuiz'
import LiveResults from '../screens/LiveResults'
import ResultsClosed from '../screens/ResultsClosed'
import Breakdown from '../screens/Breakdown'
import Analytics from '../screens/Analytics'
import Environment from '../screens/Environment'

const Stack = createNativeStackNavigator()
const Tab   = createBottomTabNavigator()

// ─── Stacks ───────────────────────────────────────────────────────────────────

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="Dashboard" component={Dashboard} />
      <Stack.Screen name="Profile"   component={Profile} />
    </Stack.Navigator>
  )
}

function AttendanceStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="AttendanceSessions" component={AttendanceSessions} />
      <Stack.Screen name="AttendanceDetail"   component={AttendanceDetail} />
    </Stack.Navigator>
  )
}

function QuizStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="QuizList"      component={QuizList} />
      <Stack.Screen name="CreateQuiz"    component={CreateQuiz} />
      <Stack.Screen name="LiveResults"   component={LiveResults} />
      <Stack.Screen name="ResultsClosed" component={ResultsClosed} />
      <Stack.Screen name="Breakdown"     component={Breakdown} />
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

function EnvStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="EnvironmentScreen" component={Environment} />
    </Stack.Navigator>
  )
}

// ─── Main tabs ────────────────────────────────────────────────────────────────

const TAB_ICONS = {
  Home:        { active: 'home',             inactive: 'home-outline' },
  Attendance:  { active: 'people',           inactive: 'people-outline' },
  Quiz:        { active: 'help-circle',      inactive: 'help-circle-outline' },
  Analytics:   { active: 'bar-chart',        inactive: 'bar-chart-outline' },
  Environment: { active: 'leaf',             inactive: 'leaf-outline' },
}

function MainTabs() {
  const { bottom } = useSafeAreaInsets()
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: C.primary,
        tabBarInactiveTintColor: C.gray400,
        tabBarStyle: {
          backgroundColor: C.card,
          borderTopWidth: 1,
          borderTopColor: C.border,
          paddingBottom: 4 + bottom,
          height: 60 + bottom,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
        },
        tabBarIcon: ({ focused, color, size }) => {
          const icons = TAB_ICONS[route.name]
          const iconName = focused ? icons.active : icons.inactive
          return <Ionicons name={iconName} size={size} color={color} />
        },
      })}
    >
      <Tab.Screen name="Home"        component={HomeStack}       options={{ title: 'Home' }} />
      <Tab.Screen name="Attendance"  component={AttendanceStack} options={{ title: 'Attendance' }} />
      <Tab.Screen name="Quiz"        component={QuizStack}       options={{ title: 'Quiz' }} />
      <Tab.Screen name="Analytics"   component={AnalyticsStack}  options={{ title: 'Analytics' }} />
      <Tab.Screen name="Environment" component={EnvStack}        options={{ title: 'Env' }} />
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
  const { state } = useLecturer()

  return (
    <NavigationContainer ref={navigationRef}>
      {state.isLoggedIn ? <MainTabs /> : <LoginStack />}
      <ToastContainer />
      <ModalRouter />
    </NavigationContainer>
  )
}
