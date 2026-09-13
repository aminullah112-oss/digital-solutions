import { ArrowUpRight } from 'lucide-react';

interface LiveProjectButtonProps {
  className?: string;
}

export default function LiveProjectButton({ className = '' }: LiveProjectButtonProps) {
  return (
    <button
      type="button"
      className={`inline-flex items-center gap-2 rounded-full border-2 border-[#D7E2EA] text-[#D7E2EA] font-medium uppercase tracking-widest px-8 py-3 sm:px-10 sm:py-3.5 text-sm sm:text-base hover:bg-[#D7E2EA]/10 transition-colors duration-200 whitespace-nowrap ${className}`}
    >
      Live Project
      <ArrowUpRight className="w-4 h-4 sm:w-5 sm:h-5" strokeWidth={2} />
    </button>
  );
}
