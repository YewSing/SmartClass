import { Platform, View, Text, TouchableOpacity, StyleSheet } from 'react-native'
import { NavigationContainer, DefaultTheme } from '@react-navigation/native'
import { createNativeStackNavigator } from '@react-navigation/native-stack'
import { createBottomTabNavigator, BottomTabBar } from '@react-navigation/bottom-tabs'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useLecturer } from '../context/LecturerContext'
import { navigationRef } from './navigationRef'
import ToastContainer from '../components/Toast'
import ModalRouter from '../components/Modals'
import SideNav from '../components/SideNav'
import { useWideLayout, SIDE_NAV_WIDTH, CONTENT_MAX_WIDTH } from '../hooks/useWideLayout'
import { C } from '../theme'

// App background behind screens (visible either side of the content column on wide screens).
const NAV_THEME = { ...DefaultTheme, colors: { ...DefaultTheme.colors, background: C.bg } }

// ─── Screens ──────────────────────────────────────────────────────────────────
import Login from '../screens/Login'
import Dashboard from '../screens/Dashboard'
import Profile from '../screens/Profile'
import ClassDetail from '../screens/ClassDetail'
import AttendanceSessions from '../screens/AttendanceSessions'
import AttendanceDetail from '../screens/AttendanceDetail'
import QuizList from '../screens/QuizList'
import CreateQuiz from '../screens/CreateQuiz'
import LiveResults from '../screens/LiveResults'
import ResultsClosed from '../screens/ResultsClosed'
import Breakdown from '../screens/Breakdown'
import Analytics from '../screens/Analytics'
import FaceVerification from '../screens/FaceVerification'
import AdminAccounts from '../screens/AdminAccounts'
import AdminAudit from '../screens/AdminAudit'
import AdminMoodleSync from '../screens/AdminMoodleSync'

const Stack = createNativeStackNavigator()
const Tab   = createBottomTabNavigator()

// ─── Stacks ───────────────────────────────────────────────────────────────────

// On wide screens each tab's content sits in a centred column instead of
// stretching across the whole window.
function useStackOptions() {
  const wide = useWideLayout()
  return wide
    ? { headerShown: false, contentStyle: { width: '100%', maxWidth: CONTENT_MAX_WIDTH, alignSelf: 'center' } }
    : { headerShown: false }
}

function HomeStack() {
  return (
    <Stack.Navigator screenOptions={useStackOptions()}>
      <Stack.Screen name="Dashboard" component={Dashboard} />
      <Stack.Screen name="Profile"   component={Profile} />
      <Stack.Screen name="ClassDetail" component={ClassDetail} />
      <Stack.Screen name="FaceVerification" component={FaceVerification} />
    </Stack.Navigator>
  )
}

function AttendanceStack() {
  return (
    <Stack.Navigator screenOptions={useStackOptions()}>
      <Stack.Screen name="AttendanceSessions" component={AttendanceSessions} />
      <Stack.Screen name="AttendanceDetail"   component={AttendanceDetail} />
    </Stack.Navigator>
  )
}

function QuizStack() {
  return (
    <Stack.Navigator screenOptions={useStackOptions()}>
      <Stack.Screen name="QuizList"     component={QuizList} />
      <Stack.Screen name="CreateQuiz"    component={CreateQuiz} />
      <Stack.Screen name="LiveResults"   component={LiveResults} />
      <Stack.Screen name="ResultsClosed" component={ResultsClosed} />
      <Stack.Screen name="Breakdown"     component={Breakdown} />
    </Stack.Navigator>
  )
}

function AnalyticsStack() {
  return (
    <Stack.Navigator screenOptions={useStackOptions()}>
      <Stack.Screen name="AnalyticsScreen" component={Analytics} />
    </Stack.Navigator>
  )
}

// ─── Main tabs ────────────────────────────────────────────────────────────────

const TAB_ICONS = {
  Home:        { active: 'home',             inactive: 'home-outline' },
  Attendance:  { active: 'people',           inactive: 'people-outline' },
  Quiz:        { active: 'help-circle',      inactive: 'help-circle-outline' },
  Analytics:   { active: 'bar-chart',        inactive: 'bar-chart-outline' },
}

// Each tab's main page. Pressing a tab goes here, rather than back to the page last left open in it.
const TAB_ROOTS = {
  Home:       'Dashboard',
  Attendance: 'AttendanceSessions',
  Quiz:       'QuizList',
  Analytics:  'AnalyticsScreen',
}

function MainTabs() {
  const { bottom } = useSafeAreaInsets()
  const wide = useWideLayout()
  return (
    <Tab.Navigator
      tabBar={props => wide ? <SideNav {...props} icons={TAB_ICONS} /> : <BottomTabBar {...props} />}
      screenListeners={({ navigation, route }) => ({
        tabPress: (e) => {
          e.preventDefault()
          navigation.navigate(route.name, { screen: TAB_ROOTS[route.name] })
        },
      })}
      sceneContainerStyle={wide ? { marginLeft: SIDE_NAV_WIDTH, backgroundColor: C.bg } : undefined}
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
    </Tab.Navigator>
  )
}

// ─── Admin area (browser only) ────────────────────────────────────────────────
// Administrators sign in with the browser-only email sign-in and land here instead of the
// lecturer screens. The server still checks the role on every admin endpoint.

const ADMIN_ICONS = {
  Accounts:     { active: 'people-circle',    inactive: 'people-circle-outline' },
  Verification: { active: 'scan-circle',      inactive: 'scan-circle-outline' },
  AuditLog:     { active: 'document-text',    inactive: 'document-text-outline' },
  MoodleSync:   { active: 'sync-circle',      inactive: 'sync-circle-outline' },
}

const ADMIN_SCREENS = {
  Accounts:     AdminAccounts,
  Verification: FaceVerification,
  AuditLog:     AdminAudit,
  MoodleSync:   AdminMoodleSync,
}

// One screen per tab, in a stack so wide screens get the same centred column
function adminStack(name) {
  return function AdminTabStack() {
    return (
      <Stack.Navigator screenOptions={useStackOptions()}>
        <Stack.Screen name={`${name}Screen`} component={ADMIN_SCREENS[name]} />
      </Stack.Navigator>
    )
  }
}
const ADMIN_STACKS = Object.fromEntries(Object.keys(ADMIN_SCREENS).map(n => [n, adminStack(n)]))

function AdminTabs() {
  const { bottom } = useSafeAreaInsets()
  const wide = useWideLayout()
  return (
    <Tab.Navigator
      tabBar={props => wide ? <SideNav {...props} icons={ADMIN_ICONS} /> : <BottomTabBar {...props} />}
      sceneContainerStyle={wide ? { marginLeft: SIDE_NAV_WIDTH, backgroundColor: C.bg } : undefined}
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
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        tabBarIcon: ({ focused, color, size }) => {
          const icons = ADMIN_ICONS[route.name]
          return <Ionicons name={focused ? icons.active : icons.inactive} size={size} color={color} />
        },
      })}
    >
      <Tab.Screen name="Accounts"     component={ADMIN_STACKS.Accounts}     options={{ title: 'Accounts' }} />
      <Tab.Screen name="Verification" component={ADMIN_STACKS.Verification} options={{ title: 'Face verification' }} />
      <Tab.Screen name="AuditLog"     component={ADMIN_STACKS.AuditLog}     options={{ title: 'Audit log' }} />
      <Tab.Screen name="MoodleSync"   component={ADMIN_STACKS.MoodleSync}   options={{ title: 'SPeCTRUM sync' }} />
    </Tab.Navigator>
  )
}

// The phone apps have no administrator sign-in (T13), but a stored admin session could still
// open here; the admin area is for the browser only.
function AdminBrowserOnly() {
  const { openModal } = useLecturer()
  const insets = useSafeAreaInsets()
  return (
    <View style={[adminStyles.center, { paddingTop: insets.top }]}>
      <Ionicons name="desktop-outline" size={40} color={C.primary} />
      <Text style={adminStyles.title}>Administration is in the browser</Text>
      <Text style={adminStyles.text}>Open SmartClass in a web browser to manage accounts, face data and the SPeCTRUM sync.</Text>
      <TouchableOpacity style={adminStyles.btn} onPress={() => openModal('signout')}>
        <Text style={adminStyles.btnText}>Sign out</Text>
      </TouchableOpacity>
    </View>
  )
}

const adminStyles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 12, backgroundColor: C.bg },
  title: { fontSize: 18, fontWeight: '700', color: C.text, textAlign: 'center' },
  text: { fontSize: 14, color: C.textSub, textAlign: 'center', lineHeight: 20 },
  btn: { backgroundColor: C.primary, borderRadius: 10, paddingVertical: 12, paddingHorizontal: 24, marginTop: 8 },
  btnText: { fontSize: 15, fontWeight: '700', color: '#fff' },
})

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
  const isAdmin = !!state.lecturer?.isAdmin

  let main = <LoginStack />
  if (state.isLoggedIn) {
    if (!isAdmin) main = <MainTabs />
    else main = Platform.OS === 'web' ? <AdminTabs /> : <AdminBrowserOnly />
  }

  return (
    <NavigationContainer ref={navigationRef} theme={NAV_THEME}>
      {main}
      <ToastContainer />
      <ModalRouter />
    </NavigationContainer>
  )
}
