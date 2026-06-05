const VARIANTS = {
  primary: 'bg-accent hover:bg-accent-dk text-white border-transparent',
  ghost:   'bg-transparent hover:bg-surface2 text-text2 hover:text-text1 border-border',
  danger:  'bg-sc-red-lt hover:bg-red-100 text-sc-red-dk border-[#f5c5c5]',
}

const SIZES = {
  sm: 'px-2.5 py-1.5 text-[12px]',
  md: 'px-3.5 py-[7px] text-[13px]',
}

export default function Button({ variant = 'primary', size = 'md', children, className = '', ...props }) {
  return (
    <button
      className={`inline-flex items-center gap-1.5 rounded-[7px] font-medium border transition-all duration-150 whitespace-nowrap cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${VARIANTS[variant]} ${SIZES[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}
