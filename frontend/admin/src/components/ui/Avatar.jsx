export function avatarInitials(name) {
  return name.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
}

export default function Avatar({ name, color, size = 'md' }) {
  const sizes = { sm: 'w-6 h-6 text-[9px]', md: 'w-[30px] h-[30px] text-[11px]', lg: 'w-18 h-18 text-[26px]' }
  return (
    <div
      className={`${sizes[size]} rounded-full flex items-center justify-center font-bold text-white flex-shrink-0`}
      style={{ background: color }}
    >
      {avatarInitials(name)}
    </div>
  )
}
