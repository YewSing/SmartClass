import { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import * as api from '../services/api'
import { notificationRoute } from '../services/dashboard'
import { C } from '../theme'

export function NotificationCentre({ navigation, service = api, routeForLink = notificationRoute }) {
  const insets = useSafeAreaInsets()
  const [items, setItems] = useState([]), [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false), [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false), [hasMore, setHasMore] = useState(false), [loadingMore, setLoadingMore] = useState(false)
  const [totalUnread, setTotalUnread] = useState(0), [failedCursor, setFailedCursor] = useState(null)
  const load = useCallback(async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true); setError('')
    try { const [page, count] = await Promise.all([service.getNotifications(), service.getNotificationUnreadCount()]); setItems(page); setTotalUnread(count); setHasMore(page.length === 50); setLoaded(true); setFailedCursor(null) } catch { setError('Notifications could not be refreshed. Your last loaded items are still here.') }
    finally { setLoading(false); setRefreshing(false) }
  }, [])
  useEffect(() => { load() }, [load])
  const loadMore = async (retryCursor = null) => {
    if (!hasMore || loadingMore || !items.length) return
    const cursor = retryCursor ?? items[items.length - 1].id
    setLoadingMore(true); setError('')
    try { const page = await service.getNotifications(cursor); setItems(current => [...current, ...page]); setHasMore(page.length === 50); setFailedCursor(null) }
    catch { setFailedCursor(cursor); setError('Older notifications could not be loaded.') } finally { setLoadingMore(false) }
  }
  const open = async item => {
    if (!item.read_at) {
      try { const updated = await service.markNotificationRead(item.id); setItems(current => current.map(n => n.id === item.id ? updated : n)); setTotalUnread(count => Math.max(0, count - 1)) } catch { setError('Could not mark this notification as read.') }
    }
    const route = routeForLink(item.link)
    if (route?.tab) navigation.navigate(route.tab, route.screen ? { screen: route.screen, params: route.params } : undefined)
    else if (route?.screen) navigation.navigate(route.screen, route.params)
  }
  const readAll = async () => { try { await service.markAllNotificationsRead(); setItems(current => current.map(n => ({ ...n, read_at: n.read_at || new Date().toISOString() }))); setTotalUnread(0) } catch { setError('Could not mark all notifications as read.') } }
  return <View style={s.page}><View style={[s.header, { paddingTop: insets.top + 10 }]}><TouchableOpacity onPress={() => navigation.goBack()} accessibilityLabel="Back"><Ionicons name="arrow-back" size={22} color={C.text} /></TouchableOpacity><View style={s.headerCopy}><Text style={s.title}>Notifications</Text><Text style={s.sub}>{totalUnread} unread</Text></View><TouchableOpacity onPress={readAll} disabled={!totalUnread}><Text style={s.readAll}>Mark all read</Text></TouchableOpacity></View>
    <ScrollView contentContainerStyle={s.content} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => load(true)} />}>
      {error ? <View style={s.error}><Ionicons name="cloud-offline-outline" size={17} color={C.redDk}/><Text style={s.errorText}>{error}</Text><TouchableOpacity onPress={() => failedCursor != null ? loadMore(failedCursor) : load()}><Text style={s.retry}>Retry</Text></TouchableOpacity></View> : null}
      {loading && !items.length ? <ActivityIndicator style={s.loader} color={C.primary} /> : null}
      {loaded && !loading && !items.length ? <View style={s.empty}><Ionicons name="notifications-outline" size={32} color={C.gray400}/><Text style={s.emptyTitle}>You’re all caught up</Text><Text style={s.emptyText}>Class, attendance and learning updates will appear here.</Text></View> : null}
      {items.map(item => <TouchableOpacity key={item.id} style={[s.item, !item.read_at && s.unread]} onPress={() => open(item)} testID="notification-item"><View style={[s.dot, { backgroundColor: item.priority === 'urgent' ? C.red : item.priority === 'important' ? C.orange : C.primary }]} /><View style={s.copy}><View style={s.itemTop}><Text style={s.itemTitle}>{item.title}</Text><Text style={s.time}>{new Date(item.created_at).toLocaleDateString()}</Text></View><Text style={s.message}>{item.message}</Text>{item.link && !routeForLink(item.link) ? <Text style={s.unavailable}>Open this update from its feature screen.</Text> : null}</View></TouchableOpacity>)}
      {hasMore ? <TouchableOpacity style={s.loadMore} onPress={() => loadMore()} disabled={loadingMore} testID="notifications-load-more"><Text style={s.loadMoreText}>{loadingMore ? 'Loading…' : 'Load older notifications'}</Text></TouchableOpacity> : null}
    </ScrollView></View>
}
export default function Notifications(props) { return <NotificationCentre {...props} /> }
const s = StyleSheet.create({ page:{flex:1,backgroundColor:C.bg},header:{flexDirection:'row',alignItems:'center',gap:12,paddingHorizontal:16,paddingBottom:14,backgroundColor:C.card,borderBottomWidth:1,borderBottomColor:C.border},headerCopy:{flex:1},title:{fontSize:22,fontWeight:'800',color:C.text},sub:{fontSize:12,color:C.textSub,marginTop:1},readAll:{fontSize:13,fontWeight:'700',color:C.primary},content:{padding:16,paddingBottom:30},error:{flexDirection:'row',alignItems:'center',gap:8,padding:12,borderRadius:10,backgroundColor:C.redLt,marginBottom:12},errorText:{flex:1,color:C.redDk,fontSize:12},retry:{fontSize:12,fontWeight:'800',color:C.redDk},loader:{marginTop:60},empty:{alignItems:'center',padding:42},emptyTitle:{fontSize:16,fontWeight:'700',color:C.text,marginTop:10},emptyText:{fontSize:13,color:C.textSub,textAlign:'center',marginTop:5,lineHeight:18},item:{flexDirection:'row',gap:11,backgroundColor:C.card,borderWidth:1,borderColor:C.border,padding:14,marginBottom:8,borderRadius:12},unread:{borderLeftWidth:4,borderLeftColor:C.primary,backgroundColor:C.blueLt},dot:{width:8,height:8,borderRadius:4,marginTop:5},copy:{flex:1},itemTop:{flexDirection:'row',gap:8},itemTitle:{flex:1,fontSize:14,fontWeight:'700',color:C.text},time:{fontSize:11,color:C.textHint},message:{fontSize:13,color:C.textSub,lineHeight:18,marginTop:4},unavailable:{fontSize:11,color:C.textHint,marginTop:7},loadMore:{minHeight:44,alignItems:'center',justifyContent:'center',borderWidth:1,borderColor:C.border,borderRadius:10,backgroundColor:C.card},loadMoreText:{fontSize:13,fontWeight:'700',color:C.primary} })
