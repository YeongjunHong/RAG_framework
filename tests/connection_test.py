import pika
import sys
import os

# --- 1. 설정 정보 (테스트 당일 백엔드 팀에게 물어볼 것) ---
BROKER_HOST = 'localhost'    # RabbitMQ 서버 IP
BROKER_PORT = 5672           # AMQP 기본 포트 (MQTT 1883 아님!)
REQ_QUEUE_NAME =  # 요청이 들어오는 큐 이름
RES_QUEUE_NAME =  # 응답을 보낼 큐 이름

def main():
    print(" [AI Worker] RabbitMQ 연결 시도 중...")
    
    # 1. 연결 생성
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=BROKER_HOST, port=BROKER_PORT)
        )
        channel = connection.channel()
    except Exception as e:
        print(f" 연결 실패: {e}")
        return

    # 2. 큐 선언 (Queue Declare)
    # 큐가 없으면 만들고, 있으면 그냥 씀. (Idempotent)
    channel.queue_declare(queue=REQ_QUEUE_NAME)
    channel.queue_declare(queue=RES_QUEUE_NAME)

    print(f" [AI Worker] 연결 성공! '{REQ_QUEUE_NAME}' 대기 중...")

    # 3. 콜백 함수 (메시지 수신 시 실행될 로직)
    def callback(ch, method, properties, body):
        message = body.decode()
        print(f"\n [수신] 내용: {message}")

        # --- 답장 보내기 (Echo) ---
        response_msg = f"Echo: {message}"
        
        # 기본 Exchange('')를 사용해 특정 큐(routing_key)로 직접 발송
        ch.basic_publish(
            exchange='',
            routing_key=RES_QUEUE_NAME,
            body=response_msg
        )
        print(f" [발신] 큐: {RES_QUEUE_NAME} | 내용: {response_msg}")
        
        # [중요] 메시지 처리 완료를 서버에 알림 (Ack)
        # 이걸 안 하면 RabbitMQ는 네가 처리를 못 했다고 생각해서 메시지를 다시 큐에 넣음
        ch.basic_ack(delivery_tag=method.delivery_tag)

    # 4. 구독 설정
    channel.basic_qos(prefetch_count=1) # 한 번에 하나씩만 처리하겠다 (공평 분배)
    channel.basic_consume(queue=REQ_QUEUE_NAME, on_message_callback=callback)

    try:
        channel.start_consuming() # 무한 루프 시작
    except KeyboardInterrupt:
        print("\n 종료 요청. 연결을 끊습니다.")
        channel.stop_consuming()
        connection.close()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)