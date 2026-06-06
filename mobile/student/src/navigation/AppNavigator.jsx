import { NavigationContainer } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import { navigationRef } from './navigationRef'
import ToastContainer from '../components/Toast'
import ModalRouter from '../components/Modals'
import { C } from '../theme'

// ─── Screens ──────────────────────────────────────────────────────────────────
import Login from '../screens/Login'
import Home from '../screens/Home'
import Attendance from '../screens/Attendance'
import AttSessionDetail from '../screens/AttSessionDetail'
import AttReportStatus from '../screens/AttReportStatus'
import Participation from '../screens/Participation'
import PartSessionPerf from '../screens/PartSessionPerf'
import Profile from '../screens/Profile'

const Stack = createNativeStackNavigator()
const Tab   = createBottomTabNavigator()

// ─── Stacks ───────────────────────────────────────────────────────────────────

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="HomeScreen" component={Home} />
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

function ParticipationStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="ParticipationScreen" component={Participation} />
      <Stack.Screen name="PartSessionPerf"     component={PartSessionPerf} />
    </Stack.Navigator>
  )
}

function ProfileStack() {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="ProfileScreen" component={Profile} />
    </Stack.Navigator>
  )
}

// ─── Main tabs ────────────────────────────────────────────────────────────────

const TAB_ICONS = {
  Home:          { active: 'home',                inactive: 'home-outline' },
  Attendance:    { active: 'calendar',            inactive: 'calendar-outline' },
  Participation: { active: 'stats-chart',         inactive: 'stats-chart-outline' },
  Profile:       { active: 'person',              inactive: 'person-outline' },
}

function MainTabs() {
  const { bottom } = useSafeAreaInsets()
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: C.primary,
        tabBarInactiveTintColor: C.textHint,
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
      <Tab.Screen name="Home"          component={HomeStack}          options={{ title: 'Home' }} />
      <Tab.Screen name="Attendance"    component={AttendanceStack}    options={{ title: 'Attendance' }} />
      <Tab.Screen name="Participation" component={ParticipationStack} options={{ title: 'Participation' }} />
      <Tab.Screen name="Profile"       component={ProfileStack}       options={{ title: 'Profile' }} />
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
      <ToastContainer />
      <ModalRouter />
    </NavigationContainer>
  )
}
