import { Server } from 'socket.io';
import { createServer } from 'http';
import { v4 as uuidv4 } from 'uuid';

interface ChatRoom {
  id: string;
  name: string;
  participants: string[];
}

interface Message {
  user: string;
  message: string;
}

const chatRooms: ChatRoom[] = [
  { id: 'public', name: 'Public Chat', participants: [] }
];

const httpServer = createServer();
const io = new Server(httpServer, {
  cors: {
    origin: "http://localhost:3000",
    methods: ["GET", "POST"]
  }
});

io.on('connection', (socket) => {
  console.log(`User connected: ${socket.id}`);

  // Send existing rooms to the newly connected client
  socket.emit('rooms update', chatRooms);

  socket.on('join room', (roomId: string) => {
    const room = chatRooms.find(r => r.id === roomId);
    if (room) {
      socket.join(roomId);
      room.participants.push(socket.id);
      console.log(`User ${socket.id} joined room ${roomId}`);
      io.emit('rooms update', chatRooms);
    } else {
      console.error(`Room ${roomId} not found`);
    }
  });

  socket.on('leave room', (roomId: string) => {
    const room = chatRooms.find(r => r.id === roomId);
    if (room) {
      socket.leave(roomId);
      room.participants = room.participants.filter(id => id !== socket.id);
      console.log(`User ${socket.id} left room ${roomId}`);
      io.emit('rooms update', chatRooms);
    } else {
      console.error(`Room ${roomId} not found`);
    }
  });

  socket.on('create private room', (otherUserId: string) => {
    const roomId = uuidv4();
    const roomName = `Private: ${socket.id} and ${otherUserId}`;
    const newRoom: ChatRoom = { id: roomId, name: roomName, participants: [socket.id, otherUserId] };
    chatRooms.push(newRoom);
    io.to(socket.id).to(otherUserId).emit('room created', newRoom);
    io.emit('rooms update', chatRooms);
  });

  socket.on('create group room', (roomName: string, participants: string[]) => {
    const roomId = uuidv4();
    const newRoom: ChatRoom = { id: roomId, name: roomName, participants };
    chatRooms.push(newRoom);
    io.emit('room created', newRoom);
    io.emit('rooms update', chatRooms);
  });

  socket.on('chat message', (msg: string, roomId: string) => {
    const room = chatRooms.find(r => r.id === roomId);
    if (room) {
      const message: Message = { user: socket.id, message: msg };
      io.to(roomId).emit('chat message', message);
    } else {
      console.error(`Room ${roomId} not found`);
    }
  });

  socket.on('disconnect', () => {
    console.log(`User disconnected: ${socket.id}`);
    // Remove user from all rooms they were in
    chatRooms.forEach(room => {
      room.participants = room.participants.filter(id => id !== socket.id);
    });
    io.emit('rooms update', chatRooms);
  });
});

const PORT = process.env.PORT || 3001;
httpServer.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
