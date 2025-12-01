import os
import httpx
import logging
import time
import datetime
from typing import Union, Literal
import asyncio

import pandas as pd
import numpy as np

# TEMP: 패키지 배포시 파이썬 경로추가 코드 제거 후 이하 모듈 임포트에 상대경로 적용
import os
import sys
EXECUTOR_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(EXECUTOR_ROOT))
sys.path.append(EXECUTOR_ROOT)
sys.path.append(PROJECT_ROOT)

from services.time_service import TimeService
from kis.api_auth.base import KISAuth, KISConfig, setup_exec_logging
from kis.client.domestic_futures.client import KisTradingAgent      # 참고: client.py 가 .client.kis.domestic_futures_
from exec_models import TradingSignal    # TODO: src.models 경로랑 겹쳐서 pylance 에서 TradingSignal 클래스 인식 안됨.
from telebot import send_tele


### executor.main.py 에서 실행할 트레이딩 수행함수 (input: 시그널, output: result)
### executor.main.py 에서 실행필요. 
# TODO: 매매 signal 키-값 정의하는 dataclass 모델 정의 필요! (dolpha1 말고, 범용 주문)
# TODO: signal: {'position': '', 'ticker': '', 'volume': '', 'target_price': ''}
async def execute_order(signal: TradingSignal, 
                        is_real: bool=True, 
                        order_method: str='market', 
                        rate_limit: float=2, 
                        logging: logging=None): 

    sleep_sec = 1 / rate_limit


    #####################
    ### Config & Auth ###
    #####################

    # config 객체 생성
    config_file = "config_real.json" if is_real else "config_paper.json"
    config_path = os.path.join(EXECUTOR_ROOT + "/kis/client/domestic_futures", 
                               config_file)
    # config_path = os.path.join(PROJECT_ROOT + "config.json")   # (HJ) ADJ: config 파일 경로 수정 테스트
    config = KISConfig(config_path=config_path)
    # (HJ) TODO: config 객체 dolpha1.py 에서 받아서 사용해보기! ("유효하지 않은 token 입니다. (EGW00121)" 해결하기 위해)

    # auth 객체 생성
    client = httpx.Client()
    # client = httpx.AsyncClient(timeout=30.0)    # 왜 httpx.AsyncClient() 는 timeout=30.0 있어야 작동하지?
    # (HJ) ADJ: executor.kis.api_auth.base.py 의 KISAuth 객체의 load_access_token() 메서드가 비동기로 작성됨! 
    auth = KISAuth(config=config, client=client)  # KISAuth 인스턴스 생성(초기화) 시 load_access_token() 호출하므로 await 추가 필요!
    
    # auth.get_access_token()   # (HJ) ADJ: KISAuth 객체의 get_access_token() 메서드만 비동기로 작성된 함수(코루틴 객체)므로, 이 코루틴 객체의 리턴은 await 명령으로 비동기 호출(리턴 대기)
    # logging.info("🔐 Access token file not found - created new access token file for the KisTradingAgent instance.")


    #####################
    ### Setup logging ###
    #####################

    # execution 로그 설정
    # setup_exec_logging(config.config_dir)     # dolpha1.py logger 와 충돌 안나도록 일단 set_logging() 미실행
    # 나중에 set_logger() 함수에 logger: logging 파라미터 추가해서 로거별 세팅 가능하도록 설정 후 위 Setup logging 코드 사용!


    #######################
    ### KisTradingAgent ###
    #######################

    kis_agent = KisTradingAgent(config=config, auth=auth)

    ### 고려사항 1. 시그널 들어오는 대로 매매 주문 및 체결확인 하는 로직 수행하는 코드
                # input: signal 
                # logic: trading (order submission & confirmation)
                # ouput: result 
                ### 함수로 만들지, main 실행파일로 만들지 고민! 
                ### main 실행파일로 만들 경우, config 파일 결정 언제하지? (real/paper 구분)
    
    ### 고려사항 2. 주문집행 1 cycle(unit) 정의 (향후 여러 cycle 비동기 또는 병렬 실행 염두)
                # 0. 매매 최소조건 확인: 잔고 예치금 1,000 만원 이상
                    # (국내선물만 해당하므로 나중에 외부 데코처리, e.g. @execute_order_kis_futures)
                # 1. 주문가능 조회: (주문가능 수량 > signal 수량) == True
                # 2. 주문 처리: 
                    # 2-1. 주문 제출: 시그널 포지션, 수량 만큼
                    # 2-2. 체결상태 확인: 


    #################################
    ### 0. 매매 최소조건 확인 및 잔고확인 ###
    #################################


    ### 매매 최소조건 확인
    # 일반투자자 국내선물옵션 기본예탁금 (최초 거래시 또는 거래재개시) (전문투자자는 기본예탁금 불필요)
    # 국내선물 기본예탁금: 1,000 만원 이상
    # 국내옵션 기본예탁금: 2,000 만원 이상

    ### 매매 기본조건
    # 종목별 개시증거금('initial' margin) 이상 현금보유 필요 (변동성 고려해서 기본 +a 금액 처리!)
    # 종목별 유지증거금('matintenance' margin) 이상 (시가)평가금액 유지 필요 (모니터링 및 알람!)

    ### 첫매매(init_trading) 판단 및 분기처리 필요!
    # monitor_signal 과 trade_signal 둘 다 (및 reason) 확인 후, 

    # 방법 1. monitor_signal 이 현재계좌잔고(조회 필요!)와 동일한지 확인 필요! (execution.py 에서 채택! <- trading_signal 로부터 order_signal 보정하는데 사용됨)
        # 동일하면, trade_signal 로 그대로 매매진행
        # 다르면, (계좌잔고 + x = monitor_signal + trade_signal) 되도록 하는 x 를 최종 order_signal 로 사용!
        # (monitor_signal - 계좌잔고 == trade_signal) 이어야 함
        # 
        
        # order_signal = trade_signal + (previous_monitor_signal - 계좌잔고)    <- 이 경우 previous_monitor_signal 필요
            # trade_signal = monitor_signal - previous_monitor_signal 이므로 
            # order_signal = monitor_signal - 계좌잔고      <- 이 경우 monitor_signal 필요!

        # 시그널에 따라 매수하는 경우 (and 계좌잔고=0 인 경우)
        # order_signal = 1 + (0 - 0)    = 1     # Exceed UB from inside
        # order_signal = 1 - 0          = 1
        # order_signal = 2 + (-1 - 0)   = 1     # Exceed UB from opposite-outside
        # order_signal = 1 - 0          = 1
        # order_signal = 1 + (-1 - 0)   = 0     # Enter LB from outside
        # order_signal = 0 - 0          = 0
        
        # 시그널에 따라 매도하는 경우 (and 계좌잔고=0 인 경우)
        # order_signal = -1 + (0 - 0)   = -1    # Exceed LB from inside
        # order_signal = -1 - 0         = -1
        # order_signal = -2 + (1 - 0)   = -1    # Exceed LB from opposite-outside
        # order_signal = -1 - 0         = -1
        # order_signal = -1 + (1 - 0)   = 0     # Enter UB from outside
        # order_signal = 0 - 0          = 0
        # 
        # x = monitor_signal + trade_signal - 계좌잔고

        ### 결론: 매매할 시그널 기준 2 가지
        ### (1) trade_signal: "n 개 사(팔아)!" 의미
        ### (2) monitor_signal (target_position): "n 개 보유하도록 매매해!" 의미
        ###     -> 매매수량(target_position - curr_position) 계산을 위해 현재계좌잔고 조회 필요!
    
    # 방법 2. # (HJ) ADJ: 포지션 변하는 경우의 8 가지 reason 의 분기마다 (dolpha1.py 에서 채택! <- trading_signal 생성에 사용됨)
        # Enter from out 인지 Exceed from inside 인지 등으로 직전 포지션 파악
            
            # Exceed UB from inside: 
            # Exceed UB from opposite-outside: 
            # Enter LB from outside: 
            # Enter VWAP from outside: 

            # Exceed LB from inside: 
            # Exceed LB from opposite-outside: 
            # Enter UB from outside: 
            # Enter VWAP from outside: 

        # 이것도 현재계좌잔고 조회 필요함. (방법 1 과 동일하게) 
        # (방법 1과 사실상 동일한 내용인데 해당 처리를 8 가지 분기에서 작성하는 것 뿐인가???)
    
    time.sleep(sleep_sec)     # TODO: 모의투자 유량 2 req/s, 실제투자 유량 5 req/s
    try:
        res_balance = kis_agent.check_balance(margin_type='initial')    # (HJ) FEAT: 포지션 진입 전 계좌잔고
        res_balance_outputs = res_balance.body.get("output1", [])
        # maintenance_balance = kis_agent.check_balance(margin_type='maintenance')    # (HJ) FEAT: 포지션 진입 후 계좌잔고

        # 유의: output1은 당일보유이력 있는 종목만 존재
        # 유의: 즉, (1) 당일매매이력이 없고 (2) 종목보유량 0 이면 output1 내용물 없음.
        # 유의: -> (1) 당일 첫매매(initial_trading)인데 (2) 종목보유량 없는 경우, 
        # 유의: -> 아래 for문 대신 balance_quantity = 0 값 직접 할당 필요! 

        # 1. 종목보유량이 있는 경우
        if len(res_balance_outputs) > 0:
            balance_history = []
            for res_balance_output in res_balance_outputs:
                if res_balance_output.get('shtn_pdno') == signal.ticker:
                    # 계좌잔고 조회시점에 선물잔고 포지션 + 상태
                    if res_balance_output.get('sll_buy_dvsn_name') == '매수':
                        balance_history.append( int(res_balance_output.get('cblc_qty')) )
                    # 계좌잔고 조회시점에 선물잔고 포지션 - 상태
                    elif res_balance_output.get('sll_buy_dvsn_name') == '매도':
                        balance_history.append( - int(res_balance_output.get('cblc_qty')) )
                    # balance_history.append(res_balance_output.get('cblc_qty'))
            balance_quantity: int = balance_history[0] if len(balance_history) > 0 else 0   # 가장 최근 보유한 개수?
        # 2. 종목보유량이 없는 경우
        else:
            balance_quantity: int = 0

        ### dolpha1 매매 주문용 시그널
        if (signal.target_position != None) and (signal.target_position != 'liquidation'): 
            order_signal = int(signal.target_position) - int(balance_quantity)
            signal.position = np.sign(order_signal)
            signal.volume = abs(order_signal)
            logging.info(f"ℹ️ Exec. step 0. 잔고수량 고려하여 order_signal({order_signal}) 주문예정")

        ### 청산(liquidation) 시그널
        elif signal.target_position == 'liquidation': 
            signal.position = - np.sign(balance_quantity)
            signal.volume = abs(balance_quantity)
            logging.info(f"ℹ️ Exec. step 0. 잔고수량({balance_quantity}) 전부 청산주문 예정")

    except Exception as e:
        logging.error(f"❌ Exec. step 0. 잔고확인 및 매매분류 에러: {e}")
        return 

    # 주문수량이 0 이면, 이후 로직 실행할 경우 에러발생! (특히 장마감 전 Liquidation Exec. 실행시)
    if signal.volume == 0:
        logging.info("ℹ️ Exec. step 0. 주문 수량이 0 이므로 주문집행 미실행.")
        return 


    #####################
    ### 1. 주문가능 조회 ###
    #####################

    time.sleep(sleep_sec)     # 모의투자 유량 2 req/s, 실제투자 유량 5 req/s
    try: 
        res_possible_order = kis_agent.check_possible_order(ticker=signal.ticker, 
                                                            position=signal.position, 
                                                            price=signal.target_price, 
                                                            order_method=order_method)
        if 'output' in res_possible_order.body:
            possible_order_output = res_possible_order.body.get('output')
            logging.info(f"ℹ️ Exec. step 1. 주문가능 조회 응답: {res_possible_order.response.__repr__()}, {'매수' if signal.position == 1 else '매도'}주문가능수량: {possible_order_output.get('tot_psbl_qty')}")  # (HJ) DEBUG: 주문가능 조회 응답 확인
        elif 'msg1' in res_possible_order.body:
            raise Exception(f"주문가능 조회 실패: {res_possible_order.body.get('msg1')} ({res_possible_order.body.get('msg_cd')})")
            return 
        else:
            raise Exception("주문가능 조회 실패: 알 수 없는 오류")
            return 

        possible_order = int( possible_order_output.get('tot_psbl_qty') )
        if possible_order < signal.volume: 
            raise Exception("주문수량이 주문가능수량보다 많습니다.")
            return  # 주문수량이 주문가능수량보다 많으면 이후 로직 실행하지 않고 함수 종료
    except Exception as e:
        logging.error(f"❌ Exec. step 1. 주문가능 조회 에러: {e}")
        return 


    ############################################################################
    ### 2. 주문 처리 (입력 signal: dict <- 포지션, 수량, 목표가, 등 정보 포함!)
    ###
    ###     _df = pd.DataFrame()
    ###     order_qty = <외부시그널 입력값>
    ###     while 체결상태 OK (또는 order_qty != 0): 
    ###         2-1. 주문 제출
    ###         2-2. 체결상태 확인: 
    ###             remained_qty = response['output1']['qty']   # <inquire-ccnl API 응답의 qty(잔량)>
    ###             if remained_qty != 0: 
    ###                 order_qty = remained_qtr
    ###         2-3. 체결완료 로깅 & 메시징: 
    ###             if tot_ccld_qty != 0: 
    ###                 체결상태 logging 에 기록 (from response['output1'])
    ###                 (주문일자, 주문시간, 주문번호, 상품번호, 호가유형명, 매매구분, 총체결수량, 평균체결가, 목표가 괴리율)
    ###                 (ord_dt, ord_tmd, odno, pdno, nmpr_type_name, trad_dvsn_name, tot_ccld_qty, avg_idx, (target_p-avg_idx)/target_p - 1)
    ###                 # 참고. 목표가괴리율()은 나중에 계산하도록 하자! 
    ###
    ############################################################################

    _df = pd.DataFrame()
    results = []
    order_dates = set()
    order_quantity = signal.volume

    while order_quantity != 0: 

        ####################
        ### 2-1. 주문 제출 ###
        ####################

        time.sleep(sleep_sec)     # 모의투자 유량 2 req/s, 실제투자 유량 5 req/s
        try: 
            res_order = kis_agent.submit_order(ticker=signal.ticker, 
                                               position=signal.position, 
                                               volume=order_quantity, 
                                               price=signal.target_price, 
                                               order_method=order_method)

            # 주문접수 시점날짜 기록
            current_datetime = TimeService.now_kst_naive()
            current_date = current_datetime.strftime('%Y%m%d')
            order_dates.add(current_date)

            if 'output' in res_order.body:
                res_order_output = res_order.body.get('output')
                ord_tmd_str = res_order_output.get('ORD_TMD')   # 주문체결시각
                ord_tmd_hms = datetime.time(hour=int(ord_tmd_str[0:2]), 
                                                     minute=int(ord_tmd_str[2:4]), 
                                                     second=int(ord_tmd_str[4:6])).strftime('%H:%M:%S')
                nmpr_type_name = '시장가' if (order_method == 'market') else '지정가'
                odno = res_order_output.get('ODNO')
                submited_order_msg = f"[{signal.ticker}] 주문접수: {'매수' if signal.position == 1 else '매도'} {order_quantity} | 접수가격: {float(signal.target_price):.1f} ({nmpr_type_name}) | 접수시간: {ord_tmd_hms} | 접수번호: {odno}"
                logging.info("✅ " + submited_order_msg)
            elif 'msg1' in res_order.body:
                raise Exception(f"{res_order.body.get('msg1')} ({res_order.body.get('msg_cd')})")
            else:
                raise Exception("알 수 없는 오류")
            results.append(res_order)
        except Exception as e:
            logging.error(f"❌ Exec. step 2-1. 주문 제출 에러: {e}")
            return 


        #######################
        ### 2-2. 체결상태 확인 ### 
        #######################

        time.sleep(sleep_sec)   # TODO: (HJ) ADJ: 주문 후 일정시간 대기 필요! (너무 빨리 조회하면, 체결내역 안잡힐 수 있음) -> 비동기 처리시 await asyncio.sleep(2) 로 변경 필요!
        start_date = min(order_dates)
        end_date = max(order_dates)
        try:
            res_order_state = kis_agent.check_order_state(ticker=signal.ticker, 
                                                          position=signal.position, 
                                                          start_date=start_date, 
                                                          end_date=end_date, 
                                                          ascending=False)  # TODO: (확인) start_date, end_date 파라미터 없이 실행 <- 오늘 값 조회되는지 확인!

            if 'output1' in res_order_state.body:
                res_order_state_outputs = res_order_state.body.get('output1')
                if len(res_order_state_outputs) != 0: 
                    # 가장 최근주문의 미체결 잔량: response 의 'output1' 리스트의 첫 번째 자료의 'qty' 키의 값
                    order_quantity = int(res_order_state_outputs[0].get('qty')) if len(res_order_state_outputs) > 0 else 0    # 주문미체결잔량 재주문 위해 order_quantity 변수 업데이트
                else:
                    logging.info(f"ℹ️ 지정된 기간({start_date}~{end_date})에 접수된 주문이 없습니다.")
                    break    # 당일 주문내역이 없는 경우 while문 종료
            elif 'msg1' in res_order_state.body:
                raise Exception(f"{res_order_state.body.get('msg1')} ({res_order_state.body.get('msg_cd')})")
            else:
                raise Exception("알 수 없는 오류")

            # order_state_list = res_order_state.get("output1", [])
            # if len(order_state_list) != 0: 
            #     # 가장 최근주문의 미체결 잔량: response 의 'output1' 리스트의 첫 번째 자료의 'qty' 키의 값
            #     order_quantity = int(order_state_list[0]['qty']) if len(order_state_list) > 0 else 0    # 주문미체결잔량 재주문 위해 order_quantity 변수 업데이트
            # else:
            #     logging.info(f"ℹ️ 지정된 기간({start_date}~{end_date})에 접수된 주문이 없습니다.")
            #     break    # 당일 주문내역이 없는 경우 while문 종료
        except Exception as e:
            logging.error(f"❌ Exec. step 2-2. 체결상태 확인 에러: {e}")
            return 

        
        ##############################
        ### 2-3. 체결완료 로깅 & 메시징 ### 
        ##############################

        # TODO: 매매주문 및 체결확인 사이클은 비동기로 짜므로, 2-3. 체결완료 로깅 & 메시징 부분은 execution.execute_order() 함수 가져다 쓰는 main 파일에서 처리하는게 맞을 듯! (여기서 처리하면, 비동기 사이클 여러개 돌릴 때 메시징 순서 꼬일 수 있음)
        # TODO: 2-3 분리 위해 execute_order() 함수 리턴값에 order_state 추가 필요! (-> executor.main.py 에서 처리하도록)
        # while 문 안에서 매매체결 확인하면서 기록 남기려면 2-3 외부처리 어려울지도..
        
        try: 
            order_state_summary = {'접수일자': res_order_state_outputs[0].get('ord_dt'), 
                                   '접수시간': res_order_state_outputs[0].get('ord_tmd'),
                                   '접수번호': res_order_state_outputs[0].get('odno'), 
                                   '상품번호': res_order_state_outputs[0].get('pdno'), 
                                   '호가유형': res_order_state_outputs[0].get('nmpr_type_name'), 
                                   '매매구분': res_order_state_outputs[0].get('trad_dvsn_name'), 
                                   '체결수량': res_order_state_outputs[0].get('tot_ccld_qty'), 
                                   '평균체결가': res_order_state_outputs[0].get('avg_idx'), 
                                   '미체결수량': res_order_state_outputs[0].get('qty')}
            if order_state_summary['체결수량'] != '0': 
                ord_tmd_hms = datetime.time(hour=int(order_state_summary['접수시간'][0:2]), 
                                            minute=int(order_state_summary['접수시간'][2:4]), 
                                            second=int(order_state_summary['접수시간'][4:6])).strftime('%H:%M:%S')
                completed_order_msg = f"[{order_state_summary['상품번호']}] 체결완료: {order_state_summary['매매구분']} {order_state_summary['체결수량']} | 체결가격: {float(order_state_summary['평균체결가']):.1f} ({order_state_summary['호가유형']}) | 접수시간: {ord_tmd_hms} | 접수번호: {order_state_summary['접수번호']}"
                # 로깅 코드
                # TODO: 체결내역 logging (1) 사전세팅 후, (2) 여기서 기록!
                logging.info("✅ " + completed_order_msg)
                # 메시징 코드
                # TODO: 텔레그램 AlphaWave Dolpha1 그룹 채팅방으로 체결내역요약 전송 
                # 메세지 예시: {'매매구분', '상품번호', '체결수량', '평균체결가', '호가유형'}
                # 메세지 예시: f"{매매구분} {상품번호} {체결수량} 계약 at W{평균체결가} ({호가유형})"
                # 메세지 예시: "매도 106W12 1 계약 at 1446.00 (시장가)"
                chat_title = "alphawave_dolpha1" if is_real else "alphawave_test" # (HJ) ADJ: (임시) 텔레그램 채팅방 구분용 클래스변수 추가
                completed_order_tele_msg = (
                    f"*\[{order_state_summary['상품번호']}\] 주문완료*\n"
                    f"체결완료: {order_state_summary['매매구분']} {order_state_summary['체결수량']}\n"
                    f"체결가격: {float(order_state_summary['평균체결가']):.1f} ({order_state_summary['호가유형']})\n"
                    f"접수시간: {order_state_summary['접수시간']}\n"
                    f"접수번호: {order_state_summary['접수번호']}"
                )
                await send_tele(msg=completed_order_tele_msg, chat_title=chat_title)  # TODO: async 함수라서 await 붙여야 하는데, 여기서는 await 못붙임. -> executor.main.py 에서 await 붙여서 호출하도록 수정 필요!
        except Exception as e:
            logging.error(f"❌ Exec. step 2-3. 체결완료 로깅 에러: {e}")

    return results      # 한투 API 선물옵션 주문[v1_국내선물-001] 요청에 대한 응답들 담은 리스트 반환