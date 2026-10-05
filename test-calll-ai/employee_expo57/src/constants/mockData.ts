export interface CallRecord {
  id: string;
  callerName: string;
  phoneNumber: string;
  type: "inbound" | "outbound" | "missed";
  timestamp: string;
  duration: string;
  aiSummary: string;
  hasRecording: boolean;
  sentiment?: "positive" | "neutral" | "negative";
}

export interface ContactItem {
  id: string;
  name: string;
  role: string;
  extension: string;
  department: "Sales" | "Support" | "Billing";
  status: "available" | "on_call" | "away";
  duration?: string;
}

export const INITIAL_ACTIVE_CALL = {
  callerName: "Ahmed Mansour",
  phoneNumber: "+20 100 123 4567",
  durationSeconds: 225, // 03:45
  sentiment: "Positive Sentiment",
  summaryBullets: [
    "Inquiry about laptop delivery",
    "Promised arrival tomorrow 2 PM"
  ]
};

export const MOCK_HISTORY: CallRecord[] = [
  {
    id: "hist-1",
    callerName: "Khaled Said",
    phoneNumber: "+20 100 589 8233",
    type: "inbound",
    timestamp: "10:45 AM",
    duration: "02:00m",
    aiSummary: "Requested return of order #8841; approved by AI",
    hasRecording: true,
    sentiment: "positive"
  },
  {
    id: "hist-2",
    callerName: "Khaled Said",
    phoneNumber: "+20 100 589 8233",
    type: "missed",
    timestamp: "10:45 AM",
    duration: "1:1h",
    aiSummary: "Discussed pricing for the new service tier; follow-up scheduled.",
    hasRecording: true,
    sentiment: "neutral"
  },
  {
    id: "hist-3",
    callerName: "Sanam Hnith",
    phoneNumber: "+20 110 539 8233",
    type: "inbound",
    timestamp: "10:45 AM",
    duration: "2h 3m",
    aiSummary: "Discussed pricing for the new service tier; follow-up scheduled.",
    hasRecording: true,
    sentiment: "positive"
  },
  {
    id: "hist-4",
    callerName: "Khaled Said",
    phoneNumber: "+20 100 538 8233",
    type: "missed",
    timestamp: "10:45 AM",
    duration: "0s",
    aiSummary: "Customer disconnected after 12s in Support queue.",
    hasRecording: false,
    sentiment: "neutral"
  },
  {
    id: "hist-5",
    callerName: "Omar Khaled",
    phoneNumber: "+20 120 445 1199",
    type: "outbound",
    timestamp: "09:30 AM",
    duration: "03:45m",
    aiSummary: "Confirmed shipping address for Cairo warehouse dispatch.",
    hasRecording: true,
    sentiment: "positive"
  }
];

export const MOCK_CONTACTS: ContactItem[] = [
  {
    id: "c-1",
    name: "Sarah Chen",
    role: "Sales Executive",
    extension: "1001",
    department: "Sales",
    status: "available"
  },
  {
    id: "c-2",
    name: "Mark Davis",
    role: "Support Specialist",
    extension: "1002",
    department: "Support",
    status: "available"
  },
  {
    id: "c-3",
    name: "James Lee",
    role: "Billing Lead",
    extension: "1003",
    department: "Billing",
    status: "on_call",
    duration: "04:15"
  },
  {
    id: "c-4",
    name: "Emily Wong",
    role: "Customer Success",
    extension: "1004",
    department: "Support",
    status: "away"
  }
];
